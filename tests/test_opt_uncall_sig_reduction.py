"""Memoria come array nelle signature + snapshot ridotto di opt-uncall.

Le procedure ricevono la memoria come unico `int __mn_mem[]`; con
--opt-uncall-user-calls lo snapshot XOR copre solo le celle scritte dal callee.
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


def _proc_params(kairos: str, proc: str) -> str:
    m = re.search(rf"^procedure {re.escape(proc)}\(([^)]*)\)", kairos, re.MULTILINE)
    return m.group(1) if m else ""


class TestSigReduction(unittest.TestCase):
    """La memoria passa come unico array `int __mn_mem[]` (per riferimento):
    nessun parametro per cella, a qualunque profondità di chiamata."""

    def _check(self, src: str, procs: list[str]) -> str:
        path = _write_c(src)
        try:
            k = compile_c_to_kairos(path)
        finally:
            os.unlink(path)
        for p in procs:
            params = _proc_params(k, p)
            self.assertEqual(params.count("int __mn_mem[]"), 1, f"{p}: {params}")
            self.assertNotRegex(params, r"__mn_mem\d", f"{p}: celle singole {params}")
        return k

    def test_leaf_fn_array_param(self) -> None:
        k = self._check("int f(int x) { return x + 1; }\n"
                        "int main(void) { int y = f(42); return y; }\n", ["f"])
        self.assertRegex(k, r"call f\(__mn_mem,")

    def test_recursive_fn_array_param(self) -> None:
        self._check("int fact(int n) { if (n <= 1) return 1; return n * fact(n - 1); }\n"
                    "int main(void) { int r = fact(5); return r; }\n", ["fact"])

    def test_transitive_array_param(self) -> None:
        self._check("int leaf(int x) { return x * 2; }\n"
                    "int mid(int x) { int a = leaf(x); int b = leaf(x + 1); return a + b; }\n"
                    "int main(void) { int r = mid(7); return r; }\n", ["leaf", "mid"])


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
            # Trova pattern: `__mn_e<N> ^= __mn_mem<M>` (snap XOR) dopo call f.
            # Ogni cella toccata da f deve avere uno snap XOR; nessun'altra.
            # Conta XOR su mem cells tra `call f` e `uncall f`.
            m = re.search(
                r"call f\([^)]+\)(.*?)uncall f\(",
                k, re.DOTALL,
            )
            self.assertIsNotNone(m, "manca pattern call f → uncall f")
            snap_section = m.group(1)
            snapped_mems = set(re.findall(r"\^=\s*__mn_mem\[(\d+)\]", snap_section))
            # f scrive solo il proprio parametro e la cella di ritorno: lo
            # snapshot non deve coprire tutta la memoria.
            self.assertGreaterEqual(len(snapped_mems), 1)
            self.assertLessEqual(len(snapped_mems), 3, f"snapshot troppo largo: {snapped_mems}")
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main()
