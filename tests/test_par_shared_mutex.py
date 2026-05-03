"""Test del controllo statico memoria condivisa + mutex per PAR a due regioni."""

from __future__ import annotations

import os
import tempfile
import unittest

from mnemo.compile import compile_c_to_kairos
from mnemo.errors import MnemoCompileError


class TestParSharedMutex(unittest.TestCase):
    def test_rejects_same_slot_without_file_mutex(self) -> None:
        src = """
typedef int pthread_mutex_t;
void mnemo_pthread_parallel2(void (*a)(void), void (*b)(void));
int x;
void f(void) { x = 1; }
void g(void) { x = 2; }
int main(void) { mnemo_pthread_parallel2(f, g); return 0; }
"""
        path = self._write_temp_c(src)
        try:
            with self.assertRaises(MnemoCompileError) as ctx:
                compile_c_to_kairos(path)
            self.assertIn("pthread_mutex_t", str(ctx.exception))
            self.assertIn("livello file", str(ctx.exception))
        finally:
            os.unlink(path)

    def test_rejects_unlocked_access_with_file_mutex_present(self) -> None:
        src = """
typedef int pthread_mutex_t;
int pthread_mutex_lock(pthread_mutex_t *m);
int pthread_mutex_unlock(pthread_mutex_t *m);
void mnemo_pthread_parallel2(void (*a)(void), void (*b)(void));
pthread_mutex_t gmu;
int x;
void f(void) { x = 1; }
void g(void) { x = 2; }
int main(void) { mnemo_pthread_parallel2(f, g); return 0; }
"""
        path = self._write_temp_c(src)
        try:
            with self.assertRaises(MnemoCompileError) as ctx:
                compile_c_to_kairos(path)
            self.assertIn("pthread_mutex_lock", str(ctx.exception))
        finally:
            os.unlink(path)

    @staticmethod
    def _write_temp_c(src: str) -> str:
        fd, path = tempfile.mkstemp(suffix=".c")
        os.close(fd)
        with open(path, "w", encoding="utf-8") as f:
            f.write(src)
        return path


if __name__ == "__main__":
    unittest.main()
