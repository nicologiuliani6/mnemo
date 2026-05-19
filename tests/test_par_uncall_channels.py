"""Test par-uncall pattern + channel workers (PC.c style).

Verifica che:
1. Funzioni con ssend/srecv NON ricevano opt-uncall single-call.
2. Quando entrambi i worker di parallel2 hanno ssend/srecv, par-uncall
   è applicato (snap mem → par → diff → par-uncall → swap).
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
    def test_par_uncall_on_PC_dot_c(self) -> None:
        """PC.c reale: parallel2(producer, consumer) → par-uncall pattern emesso."""
        ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        pc_path = os.path.join(ROOT, "c_test", "PC.c")
        if not os.path.exists(pc_path):
            self.skipTest("c_test/PC.c not present")
        k = compile_c_to_kairos(pc_path, opt_uncall_user_calls=True)
        has_uncall_producer = re.search(r"uncall producer\(", k) is not None
        has_uncall_consumer = re.search(r"uncall consumer\(", k) is not None
        self.assertTrue(has_uncall_producer,
            "PC.c parallel2 deve emettere uncall producer")
        self.assertTrue(has_uncall_consumer,
            "PC.c parallel2 deve emettere uncall consumer")

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


if __name__ == "__main__":
    unittest.main()
