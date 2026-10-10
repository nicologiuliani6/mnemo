"""Codegen del pool puntatori: array fino a `cap`, nastro di stack oltre."""

from __future__ import annotations

import unittest

from mnemo.ptr_pool_kairos import emit_ptr_pool_kairos


class TestPtrPoolEmit(unittest.TestCase):
    def test_hybrid_pool(self) -> None:
        src = emit_ptr_pool_kairos(100)
        for proc in ("__mn_pool_alloc", "__mn_pool_free", "__mn_pool_store",
                     "__mn_pool_load", "__mn_tape_move", "__mn_tape_reach"):
            self.assertIn(f"procedure {proc}", src)
        self.assertIn("int __mn_mem[]", src)
        self.assertIn("if slot < 100 then", src)
        self.assertIn("stack __mn_tl, stack __mn_tr", src)


if __name__ == "__main__":
    unittest.main()
