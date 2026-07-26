"""Regression sul codegen del pool puntatori (statico nominato + heap dinamico puro).

Modello: slot < heap_base = celle nominate `__mn_mem*` (dispatch `if slot==k`,
bancato se heap_base > ~998); slot >= heap_base = heap dinamico 100% Kairos
puro — struttura associativa (indirizzo,valore) sopra uno `stack` Kairos
(`__mn_pool_heap` + contatore `__mn_pool_heap_n`), scansione lineare O(n),
nessun opcode nativo POOLPUSH/POOLADD/POOLGET (rimossi, erano un'estensione
VM fuori dalla spec pura). Verifica strutturale (veloce): eseguire un
programma con > 998 celle nominate è troppo lento per la CI (dispatch O(N)
nell'interprete), ma il forward+heap è già coperto da test_pool_runtime_loop
e dai gcc-compat malloc.
"""

from __future__ import annotations

import unittest

from mnemo.ptr_pool_kairos import emit_ptr_pool_kairos


class TestPtrPoolEmit(unittest.TestCase):
    def test_monolithic_plus_dyn(self) -> None:
        src = emit_ptr_pool_kairos(8, 8)  # 8 celle statiche, heap >= 8 dinamico
        self.assertIn("procedure __mn_pool_store", src)
        self.assertIn("procedure __mn_pool_store_dyn", src)
        self.assertIn("procedure __mn_pool_load_dyn", src)
        self.assertIn("if slot >= 8", src)
        # heap dinamico puro: stack di record + contatore, niente opcode nativi.
        self.assertIn("stack __mn_pool_heap", src)
        self.assertIn("int __mn_pool_heap_n", src)
        for op in ("poolpush(", "pooladd(", "poolget("):
            self.assertNotIn(op, src)
        # nessun banking sotto soglia
        self.assertNotIn("__mn_pool_store_b1", src)

    def test_banked_plus_dyn(self) -> None:
        # heap_base=1000 → 2 banche (0..997, 998..999) + procedure _dyn.
        src = emit_ptr_pool_kairos(1000, 1000)
        for proc in (
            "__mn_pool_store_b0", "__mn_pool_store_b1",
            "__mn_pool_load_b0", "__mn_pool_load_b1",
            "__mn_pool_store_dyn", "__mn_pool_load_dyn",
        ):
            self.assertIn(f"procedure {proc}", src)
        self.assertIn("if slot >= 1000", src)
        # b1 copre solo le celle statiche residue [998, 1000); niente out-of-range.
        self.assertIn("__mn_mem999", src)
        self.assertNotIn("__mn_mem1000", src)

    def test_heap_base_zero_only_dyn(self) -> None:
        # Nessuna memoria nominata: solo heap dinamico, niente dispatch statico.
        src = emit_ptr_pool_kairos(0, 0)
        self.assertIn("procedure __mn_pool_store_dyn", src)
        self.assertNotIn("procedure __mn_pool_store(", src)


if __name__ == "__main__":
    unittest.main()
