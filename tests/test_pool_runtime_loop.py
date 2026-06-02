"""Regression: malloc/calloc dentro un loop a bound RUNTIME senza free.

Il numero di allocazioni non è noto a compile-time → il pool puntatori statico
non è dimensionabile (la crescita on-demand richiede un modello di memoria VM
dinamico, gated su [[1. VM Kairos: allocazione dinamica]]). Prima Mnemo
sottodimensionava il pool e produceva output ERRATO in silenzio; ora emette un
errore chiaro. Escape hatch: `--ptr-pool-size N` esplicito.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# malloc in loop a bound runtime (n = argc+4), nessun free → non dimensionabile.
_SRC_BAD = """#include <stdlib.h>
int main(int argc, char **argv) {
    int n = argc + 4;
    int s = 0, i;
    for (i = 0; i < n; i++) {
        int *p = (int *)malloc(sizeof(int) * 2);
        p[0] = i; p[1] = i * 10;
        s += p[0] + p[1];
    }
    return s & 255;
}
"""

# Stesso loop ma con free nel corpo → riuso LIFO, pool piccolo, OK.
_SRC_FREE = """#include <stdlib.h>
int main(int argc, char **argv) {
    int n = argc + 4;
    int s = 0, i;
    for (i = 0; i < n; i++) {
        int *p = (int *)malloc(sizeof(int) * 2);
        p[0] = i; p[1] = i * 10;
        s += p[0] + p[1];
        free(p);
    }
    return s & 255;
}
"""


class TestPoolRuntimeLoop(unittest.TestCase):
    def _compile(self, src: str, *extra: str) -> subprocess.CompletedProcess:
        with tempfile.NamedTemporaryFile("w", suffix=".c", delete=False) as f:
            f.write(src)
            path = f.name
        try:
            return subprocess.run(
                [".venv/bin/mnemo", "dump-kairos", path, "--stdout", *extra],
                capture_output=True, text=True, cwd=ROOT, timeout=120,
            )
        finally:
            os.unlink(path)

    def test_unbounded_loop_malloc_errors(self) -> None:
        res = self._compile(_SRC_BAD)
        self.assertNotEqual(res.returncode, 0, "deve fallire, non miscompilare")
        self.assertIn("bound runtime", res.stderr)
        self.assertIn("--ptr-pool-size", res.stderr)

    def test_explicit_pool_size_compiles(self) -> None:
        res = self._compile(_SRC_BAD, "--ptr-pool-size", "50")
        self.assertEqual(res.returncode, 0, res.stderr)

    def test_free_in_loop_compiles(self) -> None:
        res = self._compile(_SRC_FREE)
        self.assertEqual(res.returncode, 0, res.stderr)


if __name__ == "__main__":
    unittest.main()
