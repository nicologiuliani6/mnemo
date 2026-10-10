"""PAR a due regioni: memoria file-scope scritta da entrambi i rami.

Nel Kairos puro i rami di un `par` non condividono memoria scrivibile (il ramo
destro lavora su una copia delle globali): Mnemo rifiuta una globale scritta da
un ramo e usata dall'altro. I mutex sono no-op.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_SRC = """
typedef int pthread_mutex_t;
int pthread_mutex_lock(pthread_mutex_t *m);
int pthread_mutex_unlock(pthread_mutex_t *m);
void mnemo_pthread_parallel2(void (*a)(void), void (*b)(void));
pthread_mutex_t gmu;
int x;
void f(void) { pthread_mutex_lock(&gmu); x = 1; pthread_mutex_unlock(&gmu); }
void g(void) { pthread_mutex_lock(&gmu); x = 2; pthread_mutex_unlock(&gmu); }
int main(void) { mnemo_pthread_parallel2(f, g); return 0; }
"""


class TestParSharedMutex(unittest.TestCase):
    def test_shared_write_rejected(self) -> None:
        with tempfile.NamedTemporaryFile("w", suffix=".c", delete=False) as f:
            f.write(_SRC)
            path = f.name
        try:
            res = subprocess.run(
                [".venv/bin/mnemo", "run", path],
                capture_output=True, text=True, cwd=ROOT, timeout=120,
            )
        finally:
            os.unlink(path)
            k = path[:-2] + ".kairos"
            if os.path.exists(k):
                os.unlink(k)
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("non condividono", res.stdout + res.stderr)


if __name__ == "__main__":
    unittest.main()
