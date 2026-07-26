"""Performance regression test: encrypt --opt-uncall-user-calls
must complete within 3x baseline. Catches VM regressions."""

from __future__ import annotations

import os
import subprocess
import time
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@unittest.skipUnless(
    os.path.exists(os.path.join(ROOT, "tests/c/repro/encrypt.c")),
    "encrypt.c not present"
)
class TestEncryptPerf(unittest.TestCase):
    MAX_RATIO = 3.0  # opt deve essere <3x baseline. Stato attuale ~1.0x.

    # Timeout bump (era 120s): migrazione Kairos puro (rimozione mnhalve/
    # mnsplit32 nativi, vedi lib/bits.kairos e lib/divmod.kairos) rende
    # and_into/or_into/shr_into O(k^2 log a)/O(n log a) invece di O(k^2)/O(n)
    # con halving nativo O(1) — costo intrinseco, non un regressione VM.
    # encrypt.c (DES-like, molte and/or/shr per round) passa da ~4s a ~190s
    # in modalità interpretata pura (sia baseline che opt, ratio invariato
    # ~1.0x — l'overhead è nel primitivo di halving condiviso da entrambi i
    # path, non nell'opt-uncall stesso).
    RUN_TIMEOUT = 300

    def _run(self, opt: bool) -> tuple[float, str]:
        cmd = [".venv/bin/mnemo", "run", "tests/c/repro/encrypt.c"]
        if opt:
            cmd.append("--opt-uncall-user-calls")
        t0 = time.perf_counter()
        res = subprocess.run(
            cmd, capture_output=True, text=True, cwd=ROOT, timeout=self.RUN_TIMEOUT
        )
        dt = time.perf_counter() - t0
        return dt, res.stdout

    def test_encrypt_opt_ratio_under_max(self) -> None:
        baseline_dt, baseline_out = self._run(opt=False)
        opt_dt, opt_out = self._run(opt=True)
        self.assertEqual(baseline_out.strip(), opt_out.strip(),
            "output baseline e opt devono coincidere")
        self.assertIn("cipher: 16713", baseline_out)
        ratio = opt_dt / baseline_dt
        self.assertLess(
            ratio, self.MAX_RATIO,
            f"opt-uncall encrypt: ratio {ratio:.2f}x > MAX_RATIO {self.MAX_RATIO}x "
            f"(base={baseline_dt:.1f}s opt={opt_dt:.1f}s)"
        )


if __name__ == "__main__":
    unittest.main()
