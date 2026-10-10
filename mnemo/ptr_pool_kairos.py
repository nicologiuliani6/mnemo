"""
Procedure `__mn_pool_*` del pool puntatori, sopra l'array Kairos `__mn_mem`.

Tutta la memoria del programma (variabili nominate e heap di malloc) sta in un
unico array `int __mn_mem[N]` (vedi `arrayize.py`): un puntatore è un indice,
quindi load/store sono un accesso diretto `__mn_mem[slot]`, O(1).

Modello malloc a header: ogni malloc di nblk celle occupa nblk+1 celle a partire
da `ctr`: mem[ctr]=nblk (header, scritto dal lowering), mem[ctr+1..] = dati; il
puntatore restituito è ctr+1.
"""

from __future__ import annotations


def emit_ptr_pool_kairos() -> str:
    return "\n".join(
        [
            "// Pool puntatori Mnemo: memoria = array __mn_mem, puntatore = indice.",
            "procedure __mn_pool_alloc(int ctr, int out_slot, int nblk, stack __mn_hist, stack __mn_scratch)",
            "    push(out_slot, __mn_hist)",
            "    out_slot += ctr",
            "    out_slot += 1",
            "    ctr += nblk",
            "    ctr += 1",
            "",
            "procedure __mn_pool_free(int slot, int ctr, int nblk, stack __mn_hist, stack __mn_scratch)",
            "    local int ctr0 = 0",
            "        ctr0 += ctr",
            "    local int last = 0",
            "        last += slot",
            "        last += nblk",
            "        if ctr0 == last then",
            "            ctr -= nblk",
            "            ctr -= 1",
            "        fi ctr0 == last",
            "        push(last, __mn_hist)",
            "    delocal int last = 0",
            "        push(ctr0, __mn_hist)",
            "    delocal int ctr0 = 0",
            "",
            "procedure __mn_pool_store(int slot, int val, int __mn_mem[], stack __mn_hist, stack __mn_scratch)",
            "    local int t = 0",
            "        t += __mn_mem[slot]",
            "        __mn_mem[slot] -= t",
            "        push(t, __mn_hist)",
            "    delocal int t = 0",
            "    __mn_mem[slot] += val",
            "",
            "procedure __mn_pool_load(int slot, int __mn_mem[], int out, stack __mn_hist, stack __mn_scratch)",
            "    local int t = 0",
            "        t += __mn_mem[slot]",
            "        push(out, __mn_hist)",
            "        out += t",
            "        push(t, __mn_hist)",
            "    delocal int t = 0",
            "",
        ]
    )
