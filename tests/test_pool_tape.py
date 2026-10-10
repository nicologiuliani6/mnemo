"""Heap oltre l'array `__mn_mem`: le celle in più finiscono sul nastro di stack.

301 blocchi da 4 int (+ header) = 1505 celle, più dell'array (named + 1024):
le ultime ~480 stanno sul nastro. Risultato come gcc con argc=1, anche
invertendo l'intero programma.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_SRC = """#include <stdio.h>
#include <stdlib.h>
int main(int argc, char **argv) {
    int n = 300 + argc;
    int *blk[400];
    long s = 0;
    for (int i = 0; i < n; i++) {
        blk[i] = (int *)malloc(sizeof(int) * 4);
        for (int k = 0; k < 4; k++) blk[i][k] = i * 10 + k;
    }
    for (int i = n - 1; i >= 0; i -= 7) s += blk[i][3] - blk[i][0];
    s += blk[0][2] + blk[n - 1][1];
    printf("%ld\\n", s);
    return 0;
}
"""


class TestPoolTape(unittest.TestCase):
    def _run(self, *extra: str) -> subprocess.CompletedProcess:
        with tempfile.NamedTemporaryFile("w", suffix=".c", delete=False) as f:
            f.write(_SRC)
            path = f.name
        try:
            return subprocess.run(
                [".venv/bin/mnemo", "run", path, "--main-argc", "1", *extra],
                capture_output=True, text=True, cwd=ROOT, timeout=300,
            )
        finally:
            os.unlink(path)
            k = path[:-2] + ".kairos"
            if os.path.exists(k):
                os.unlink(k)

    def test_spill_forward(self) -> None:
        res = self._run()
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertEqual(res.stdout.strip(), "3132")

    def test_spill_invertible(self) -> None:
        res = self._run("--check-invertibility")
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertEqual(res.stdout.strip(), "3132")


if __name__ == "__main__":
    unittest.main()
