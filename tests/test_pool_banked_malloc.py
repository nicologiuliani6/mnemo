"""Regression: malloc col modello header sul pool BANCATO (> ~998 celle).

Il pool bancato dispatcha slot→(banca,offset) con __mn_divmod_nonneg. Due bug
risolti: (1) divmod non auto-incluso se il C non usa `/` → SEGV in get_findex;
(2) l'header store passava `__mn_pool_ctr` diretto al divmod che ne consuma il
dividendo → ctr azzerato → slot drift. Forza la banca con --ptr-pool-size 1500.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_SRC = """#include <stdlib.h>
int main(void) {
    int *a = malloc(sizeof(int) * 3);
    int *b = malloc(sizeof(int) * 3);   /* concorrente con a, multi-cella */
    a[0] = 1; a[1] = 2; a[2] = 3;
    b[0] = 10; b[1] = 20; b[2] = 30;
    int r = a[0] + a[1] + a[2] + b[0] + b[1] + b[2];  /* 66 */
    free(b); free(a);
    return r & 255;
}
"""


class TestPoolBankedMalloc(unittest.TestCase):
    def _run(self, *extra: str) -> int:
        with tempfile.NamedTemporaryFile("w", suffix=".c", delete=False) as f:
            f.write(_SRC)
            path = f.name
        try:
            res = subprocess.run(
                [".venv/bin/mnemo", "run", path, "--ptr-pool-size", "1500", *extra],
                capture_output=True, text=True, cwd=ROOT, timeout=120,
            )
            return res.returncode
        finally:
            os.unlink(path)

    def test_banked_concurrent_malloc(self) -> None:
        self.assertEqual(self._run(), 66, "malloc concorrenti su pool bancato")

    def test_banked_malloc_invertible(self) -> None:
        self.assertEqual(
            self._run("--check-invertibility"), 66,
            "round-trip inverso su pool bancato",
        )


if __name__ == "__main__":
    unittest.main()
