"""Regression: malloc/calloc dentro un loop a bound RUNTIME senza free.

Il pool puntatori vive su un heap VM dinamico (`vm->mn_pool`) che cresce
on-demand: il numero di allocazioni NON deve essere noto a compile-time.
Prima questo caso o miscompilava in silenzio o (dopo la diagnostica) richiedeva
`--ptr-pool-size`; ora funziona senza flag, forward E `--check-invertibility`.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# n = argc + 4 (bound runtime), nessun free → allocazioni accumulate.
# s = sum_{i=0}^{n-1} (i + i*10) = 11 * n(n-1)/2.  argc=4 → n=8 → 11*28 = 308.
_SRC_BAD = """#include <stdlib.h>
int main(int argc, char **argv) {
    int n = argc + 4;
    int s = 0, i;
    for (i = 0; i < n; i++) {
        int *p = (int *)malloc(sizeof(int) * 2);
        p[0] = i; p[1] = i * 10;
        s += p[0] + p[1];
    }
    printf("%d\\n", s);
    return 0;
}
"""


class TestPoolRuntimeLoop(unittest.TestCase):
    def _run(self, src: str, *extra: str) -> subprocess.CompletedProcess:
        with tempfile.NamedTemporaryFile("w", suffix=".c", delete=False) as f:
            f.write(src)
            path = f.name
        try:
            return subprocess.run(
                [".venv/bin/mnemo", "run", path, "--main-argc", "4", *extra],
                capture_output=True, text=True, cwd=ROOT, timeout=120,
            )
        finally:
            os.unlink(path)

    def test_runtime_loop_no_flag(self) -> None:
        """Nessun --ptr-pool-size: il pool dinamico cresce da solo."""
        res = self._run(_SRC_BAD)
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("308", res.stdout)

    def test_runtime_loop_invertible(self) -> None:
        res = self._run(_SRC_BAD, "--check-invertibility")
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("308", res.stdout)

    def test_runtime_loop_larger(self) -> None:
        """argc=20 → n=24 → 11 * 24*23/2 = 11*276 = 3036 (pool cresce oltre l'iniziale)."""
        with tempfile.NamedTemporaryFile("w", suffix=".c", delete=False) as f:
            f.write(_SRC_BAD)
            path = f.name
        try:
            res = subprocess.run(
                [".venv/bin/mnemo", "run", path, "--main-argc", "20"],
                capture_output=True, text=True, cwd=ROOT, timeout=120,
            )
            self.assertEqual(res.returncode, 0, res.stderr)
            self.assertIn("3036", res.stdout)
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main()
