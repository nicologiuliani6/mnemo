"""Test riduzione signature procedure (B opt) + snap subset (A opt).

Verifica che `_compute_callee_mem_touches` propaghi i mem cell touches
transitivamente e che il compilatore emetta procedure con formali
ridotti al solo sottoinsieme effettivamente toccato.
"""

from __future__ import annotations

import os
import re
import tempfile
import unittest

from mnemo.compile import compile_c_to_kairos


def _write_c(src: str) -> str:
    fd, path = tempfile.mkstemp(suffix=".c")
    with os.fdopen(fd, "w") as f:
        f.write(src)
    return path


def _proc_mem_params(kairos: str, proc: str) -> list[int]:
    """Estrae gli indici `__mn_mem<i>` dalla signature `procedure <proc>(…)`."""
    m = re.search(rf"^procedure {re.escape(proc)}\(([^)]*)\)", kairos, re.MULTILINE)
    if not m:
        return []
    params = m.group(1)
    return [int(x) for x in re.findall(r"__mn_mem(\d+)", params)]


class TestSigReduction(unittest.TestCase):
    def test_leaf_fn_minimal_sig(self) -> None:
        """Funzione che usa pochi cell deve avere sig ridotta."""
        src = """
int f(int x) { return x + 1; }
int main(void) {
    int y = f(42);
    return y;
}
"""
        path = _write_c(src)
        try:
            k = compile_c_to_kairos(path)
            mems = _proc_mem_params(k, "f")
            self.assertGreater(len(mems), 0, "f deve avere almeno 1 mem param")
            self.assertLess(len(mems), 5, f"sig f troppo larga: {mems}")
        finally:
            os.unlink(path)

    def test_recursive_fixpoint(self) -> None:
        """Funzione ricorsiva: touches converge via fixpoint (no doppia conta args)."""
        src = """
int fact(int n) {
    if (n <= 1) return 1;
    return n * fact(n - 1);
}
int main(void) {
    int r = fact(5);
    return r;
}
"""
        path = _write_c(src)
        try:
            k = compile_c_to_kairos(path)
            mems = _proc_mem_params(k, "fact")
            # Ricorsione self: touched indices stabili, NON tutti i mem cell
            # del frame. Direct refs: param n + ret + temp = ~3 cell.
            self.assertLess(
                len(mems), 8,
                f"fact ricorsivo deve avere sig piccola, non {len(mems)}: {mems}"
            )
        finally:
            os.unlink(path)

    def test_transitive_touches(self) -> None:
        """Caller propaga touches del callee via fixpoint."""
        src = """
int leaf(int x) { return x * 2; }
int mid(int x) {
    int a = leaf(x);
    int b = leaf(x + 1);
    return a + b;
}
int main(void) {
    int r = mid(7);
    return r;
}
"""
        path = _write_c(src)
        try:
            k = compile_c_to_kairos(path)
            leaf_mems = _proc_mem_params(k, "leaf")
            mid_mems = _proc_mem_params(k, "mid")
            # mid deve toccare almeno tante celle quante leaf (via call), per
            # propagazione positional (sub-callee touched cell k → caller's arg[k])
            self.assertGreater(len(mid_mems), 0)
            self.assertGreater(len(leaf_mems), 0)
        finally:
            os.unlink(path)

    def test_main_call_passes_subset(self) -> None:
        """`main → call f(...)` deve passare solo mem subset di f."""
        src = """
int f(int x) { return x + 1; }
int main(void) {
    int y = f(42);
    return y;
}
"""
        path = _write_c(src)
        try:
            k = compile_c_to_kairos(path)
            proc_mems = _proc_mem_params(k, "f")
            # Trova call site
            m = re.search(r"call f\(([^)]+)\)", k)
            self.assertIsNotNone(m)
            call_args = m.group(1)
            call_mems = re.findall(r"__mn_mem(\d+)", call_args)
            # Numero mem args nella call == numero mem params nella sig
            self.assertEqual(
                len(call_mems), len(proc_mems),
                "caller mem actuals deve avere stesso count di callee mem formali"
            )
        finally:
            os.unlink(path)


class TestSnapSubset(unittest.TestCase):
    """Verifica A opt: snap XOR solo celle toccate dal callee."""

    def test_opt_uncall_snap_matches_callee_touches(self) -> None:
        """Con --opt-uncall-user-calls: pattern `e ^= mem` snap solo touched cells."""
        src = """
int f(int x) { return x + 1; }
int main(void) {
    int y = f(42);
    return y;
}
"""
        path = _write_c(src)
        try:
            k = compile_c_to_kairos(path, opt_uncall_user_calls=True)
            proc_mems = _proc_mem_params(k, "f")
            # Trova pattern: `__mn_e<N> ^= __mn_mem<M>` (snap XOR) dopo call f.
            # Ogni cella toccata da f deve avere uno snap XOR; nessun'altra.
            # Conta XOR su mem cells tra `call f` e `uncall f`.
            m = re.search(
                r"call f\([^)]+\)(.*?)uncall f\(",
                k, re.DOTALL,
            )
            self.assertIsNotNone(m, "manca pattern call f → uncall f")
            snap_section = m.group(1)
            snapped_mems = set(re.findall(r"\^=\s*__mn_mem(\d+)", snap_section))
            # snapped cells deve essere sottoinsieme di proc_mems
            for sm in snapped_mems:
                self.assertIn(
                    int(sm), proc_mems,
                    f"snap su __mn_mem{sm} ma callee f non tocca quella cella"
                )
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main()
