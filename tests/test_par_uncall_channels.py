"""Test par-uncall pattern + channel workers (PC.c style).

Verifica che:
1. Funzioni con ssend/srecv NON ricevano opt-uncall single-call (single-call
   pattern fa snap+uncall in caller, semantica spezza con canali).
2. PC.c con --opt-uncall-user-calls riceve par-uncall (pattern par-uncall su
   thread cloni funziona dopo fix collect_loops vm_invert.h: il bug MINEQ NULL
   su loop counter veniva da collect_loops che non gestiva from-loop nested).
3. Funzioni senza ssend/srecv ricevono opt-uncall normalmente.
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


class TestParUncallChannels(unittest.TestCase):
    def test_PC_dot_c_opt_uncall_par_uncall_for_channel_workers(self) -> None:
        """PC.c con opt-uncall: par-uncall NON emesso per producer/consumer
        (escluso perché usano pool ops indirettamente via printf %d runtime).

        Pool ops in inverse esecuzione (DELOCAL var=t) non roundtrip su layout
        grandi (kernel.c 370 cells); exclusion preventiva per correttezza.
        PC.c runtime resta funzionale (par regolare senza opt-uncall).
        """
        ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        pc_path = os.path.join(ROOT, "tests/c/repro", "PC.c")
        if not os.path.exists(pc_path):
            self.skipTest("tests/c/repro/PC.c not present")
        k = compile_c_to_kairos(pc_path, opt_uncall_user_calls=True)
        has_uncall_producer = re.search(r"uncall producer\(", k) is not None
        has_uncall_consumer = re.search(r"uncall consumer\(", k) is not None
        self.assertFalse(
            has_uncall_producer,
            "PC.c: par-uncall su producer deve essere ESCLUSO (pool ops)",
        )
        self.assertFalse(
            has_uncall_consumer,
            "PC.c: par-uncall su consumer deve essere ESCLUSO (pool ops)",
        )

    def test_non_channel_fn_keeps_opt_uncall(self) -> None:
        """Funzione pure-int senza canali continua ad avere opt-uncall."""
        src = """
int f(int x) { return x + 1; }
int main(void) {
    int r = f(42);
    return r;
}
"""
        path = _write_c(src)
        try:
            k = compile_c_to_kairos(path, opt_uncall_user_calls=True)
            self.assertIn("uncall f(", k,
                "Funzione int->int senza canali deve avere opt-uncall pattern")
        finally:
            os.unlink(path)

    def test_non_channel_parallel2_keeps_par_uncall(self) -> None:
        """parallel2 con worker senza canali continua ad avere par-uncall."""
        src = """
void mnemo_pthread_parallel2(void (*a)(int), void (*b)(int), int arg_a, int arg_b);
void f(int x) { int t = x; t += 1; t -= 1; }
void g(int x) { int t = x; t += 2; t -= 2; }
int main(void) {
    mnemo_pthread_parallel2(f, g, 1, 2);
    return 0;
}
"""
        path = _write_c(src)
        try:
            k = compile_c_to_kairos(path, opt_uncall_user_calls=True)
            self.assertRegex(
                k,
                r"uncall f\(",
                "parallel2 pure-int → par-uncall deve essere emesso",
            )
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main()
