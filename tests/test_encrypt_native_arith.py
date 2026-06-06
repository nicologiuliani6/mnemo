"""Regression: encrypt with --opt-uncall-user-calls and --native-arith.

VM native CALL skips library bytecode; invert_op_to_line must use the
matching native inverse (Kairos vm_invert.h INVOP_CALL), not full bytecode
inversion — otherwise DELOCAL errors and silent exit 1.
"""

from __future__ import annotations

import os
import subprocess
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@unittest.skipUnless(
    os.path.exists(os.path.join(ROOT, "tests/c/repro/encrypt.c")),
    "encrypt.c not present",
)
class TestEncryptNativeArith(unittest.TestCase):
    EXPECTED = "cipher: 16713\nL: 22  R: 10\n"

    def _run(self, *extra: str) -> subprocess.CompletedProcess[str]:
        cmd = [".venv/bin/mnemo", "run", "tests/c/repro/encrypt.c", *extra]
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=ROOT,
            timeout=120,
        )

    def test_encrypt_opt_uncall_and_native_arith(self) -> None:
        res = self._run("--opt-uncall-user-calls", "--native-arith")
        self.assertEqual(res.returncode, 0, res.stderr or res.stdout)
        self.assertEqual(res.stdout, self.EXPECTED)

    def test_encrypt_opt_uncall_native_arith_vm_dump(self) -> None:
        res = self._run(
            "--opt-uncall-user-calls",
            "--native-arith",
            "--vm-dump",
        )
        self.assertEqual(res.returncode, 0, res.stderr or res.stdout)
        self.assertIn("cipher: 16713", res.stdout)
        self.assertIn("=== VM dump ===", res.stdout)


if __name__ == "__main__":
    unittest.main()
