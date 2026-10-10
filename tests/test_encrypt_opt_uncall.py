"""Regression: encrypt with --opt-uncall-user-calls (call + snapshot + uncall)."""

from __future__ import annotations

import os
import subprocess
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@unittest.skipUnless(
    os.path.exists(os.path.join(ROOT, "tests/c/repro/encrypt.c")),
    "encrypt.c not present",
)
class TestEncryptOptUncall(unittest.TestCase):
    EXPECTED = "cipher: 16713\nL: 22  R: 10\n"

    def _run(self, *extra: str) -> subprocess.CompletedProcess[str]:
        cmd = [".venv/bin/mnemo", "run", "tests/c/repro/encrypt.c", *extra]
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=ROOT,
            timeout=600,
        )

    def test_encrypt_opt_uncall(self) -> None:
        res = self._run("--opt-uncall-user-calls")
        self.assertEqual(res.returncode, 0, res.stderr or res.stdout)
        self.assertEqual(res.stdout, self.EXPECTED)

    def test_encrypt_opt_uncall_vm_dump(self) -> None:
        res = self._run("--opt-uncall-user-calls", "--vm-dump")
        self.assertEqual(res.returncode, 0, res.stderr or res.stdout)
        self.assertIn("cipher: 16713", res.stdout)
        self.assertIn("=== VM dump ===", res.stdout)


if __name__ == "__main__":
    unittest.main()
