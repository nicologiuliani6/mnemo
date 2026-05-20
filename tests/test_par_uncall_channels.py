"""Test par-uncall pattern + channel workers (PC.c style).

Verifica che:
1. Funzioni con ssend/srecv NON ricevano opt-uncall single-call.
2. PC.c con --opt-uncall-user-calls produce esecuzione corretta (exit 0):
   il pattern par-uncall su worker con canali è disabilitato perché
   l'inverse VM panics con MINEQ NULL su loop counter (bug VM, da fixare
   in vm_invert.h interaction con par-inverse cloned frames).
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
    def test_PC_dot_c_opt_uncall_no_par_uncall_for_channel_workers(self) -> None:
        """PC.c con opt-uncall: par-uncall NON emesso per producer/consumer (usano canali).

        Il pattern par-uncall su worker channel-using crasha il VM (MINEQ NULL su
        loop counter durante invert_op_to_line di frame clonato in thread inverso).
        """
        ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        pc_path = os.path.join(ROOT, "c_test", "PC.c")
        if not os.path.exists(pc_path):
            self.skipTest("c_test/PC.c not present")
        k = compile_c_to_kairos(pc_path, opt_uncall_user_calls=True)
        has_uncall_producer = re.search(r"uncall producer\(", k) is not None
        has_uncall_consumer = re.search(r"uncall consumer\(", k) is not None
        self.assertFalse(
            has_uncall_producer,
            "PC.c: par-uncall su producer (channel-using) deve essere disabilitato",
        )
        self.assertFalse(
            has_uncall_consumer,
            "PC.c: par-uncall su consumer (channel-using) deve essere disabilitato",
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
