"""Codegen del pool puntatori: load/store diretti sull'array `__mn_mem`."""

from __future__ import annotations

import unittest

from mnemo.ptr_pool_kairos import emit_ptr_pool_kairos


class TestPtrPoolEmit(unittest.TestCase):
    def test_array_pool(self) -> None:
        src = emit_ptr_pool_kairos()
        for proc in ("__mn_pool_alloc", "__mn_pool_free", "__mn_pool_store", "__mn_pool_load"):
            self.assertIn(f"procedure {proc}", src)
        self.assertIn("int __mn_mem[]", src)
        self.assertIn("__mn_mem[slot]", src)
        self.assertNotIn("_dyn", src)


if __name__ == "__main__":
    unittest.main()
