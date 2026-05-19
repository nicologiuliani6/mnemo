"""Performance regression test: encrypt --opt-uncall-user-calls
must complete within 3x baseline. Catches VM regressions."""

from __future__ import annotations

import os
import subprocess
import time
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@unittest.skipUnless(
    os.path.exists(os.path.join(ROOT, "c_test/encrypt.c")),
    "encrypt.c not present"
)
class TestEncryptPerf(unittest.TestCase):
    MAX_RATIO = 3.0  # opt deve essere <3x baseline. Stato attuale ~2.4x.

    def _run(self, opt: bool) -> tuple[float, str]:
        cmd = [".venv/bin/mnemo", "run", "c_test/encrypt.c"]
        if opt:
            cmd.append("--opt-uncall-user-calls")
        t0 = time.perf_counter()
        res = subprocess.run(
            cmd, capture_output=True, text=True, cwd=ROOT, timeout=120
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
