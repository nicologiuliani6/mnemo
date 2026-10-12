"""
Procedure `__mn_pool_*` del pool puntatori: heap ibrido, illimitato.

Un puntatore è un indice di memoria. Gli indici sotto `cap` (variabili nominate
e la prima parte dell'heap di malloc) stanno nell'array Kairos `__mn_mem[cap]`:
accesso diretto, O(1). Gli indici da `cap` in su stanno su un **nastro** fatto di
due stack Kairos con un cursore in mezzo (zipper):

    tl: celle 0 … tc-1 del nastro (in cima la tc-1)
    tr: celle tc … tn-1           (in cima la tc)

Raggiungere la cella r sposta il cursore di |r - tc| celle, quindi costa la
distanza dall'accesso precedente (scorrere un blocco costa O(1) per cella); il
nastro si allunga con celle a zero quando serve. Tutto è Kairos puro e
reversibile: gli spostamenti sono cicli a conteggio noto, gli scarti finiscono
su `__mn_hist`.

Modello malloc a header: un blocco di nblk celle occupa nblk+1 celle da `ctr`:
mem[ctr] = nblk (scritto dal lowering), il puntatore restituito è ctr+1.
"""

from __future__ import annotations

TAPE_PARAMS = "stack __mn_tl, stack __mn_tr, int __mn_tc, int __mn_tn"
TAPE_ARGS = "__mn_tl, __mn_tr, __mn_tc, __mn_tn"


def emit_ptr_pool_kairos(cap: int) -> str:
    h = "stack __mn_hist, stack __mn_scratch"
    hs = "__mn_hist, __mn_scratch"

    def tape_branch(body: list[str]) -> list[str]:
        """Accesso alla cella di nastro r = slot - cap: `body` la trova in v
        (estratta dalla cima di tr, v deve tornare su tr)."""
        return [
            "        local int r = 0",
            f"        r += (slot - {cap})",
            f"        call __mn_tape_reach(r, {TAPE_ARGS}, {hs})",
            f"        call __mn_tape_move(r, {TAPE_ARGS}, {hs})",
            "        local int v = 0",
            "        pop(v, __mn_tr)",
            *body,
            "        push(v, __mn_tr)",
            "        delocal int v = 0",
            f"        r -= (slot - {cap})",
            "        delocal int r = 0",
        ]

    lines = [
        f"// Mnemo pointer pool: cells < {cap} in the __mn_mem array, the others on the tape.",
        f"procedure __mn_pool_alloc(int ctr, int out_slot, int nblk, {h})",
        "    push(out_slot, __mn_hist)",
        "    out_slot += ctr",
        "    out_slot += 1",
        "    ctr += nblk",
        "    ctr += 1",
        "",
        f"procedure __mn_pool_free(int slot, int ctr, int nblk, {h})",
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
        "// Tape cursor on r (0 <= r <= tn): cells 0..r-1 in tl, cell r on top of tr.",
        f"procedure __mn_tape_move(int r, {TAPE_PARAMS}, {h})",
        "    local int dr = 0",
        "    dr += ((r - __mn_tc) * ((r - __mn_tc) > 0))",
        "    local int dl = 0",
        "    dl += ((__mn_tc - r) * ((__mn_tc - r) > 0))",
        "    if dr != 0 then",
        "        local int k = 0",
        "        from k == 0 do",
        "            local int v = 0",
        "            pop(v, __mn_tr)",
        "            push(v, __mn_tl)",
        "            delocal int v = 0",
        "            k += 1",
        "        loop until k == dr",
        "        delocal int k = dr",
        "        __mn_tc += dr",
        "    fi dr != 0",
        "    if dl != 0 then",
        "        local int k = 0",
        "        from k == 0 do",
        "            local int v = 0",
        "            pop(v, __mn_tl)",
        "            push(v, __mn_tr)",
        "            delocal int v = 0",
        "            k += 1",
        "        loop until k == dl",
        "        delocal int k = dl",
        "        __mn_tc -= dl",
        "    fi dl != 0",
        "    push(dl, __mn_hist)",
        "    delocal int dl = 0",
        "    push(dr, __mn_hist)",
        "    delocal int dr = 0",
        "",
        "// Grow the tape with zero cells until it contains cell r (tn > r).",
        f"procedure __mn_tape_reach(int r, {TAPE_PARAMS}, {h})",
        "    local int e = 0",
        "    e += (((r + 1) - __mn_tn) * (((r + 1) - __mn_tn) > 0))",
        "    if e != 0 then",
        # Gli argomenti di una call devono essere distinti: la fine del nastro
        # passa a __mn_tape_move tramite una copia.
        "        local int n = 0",
        "        n += __mn_tn",
        f"        call __mn_tape_move(n, {TAPE_ARGS}, {hs})",
        "        n -= __mn_tn",
        "        delocal int n = 0",
        "        local int k = 0",
        "        from k == 0 do",
        "            local int z = 0",
        "            push(z, __mn_tl)",
        "            delocal int z = 0",
        "            __mn_tc += 1",
        "            __mn_tn += 1",
        "            k += 1",
        "        loop until k == e",
        "        delocal int k = e",
        "    fi e != 0",
        "    push(e, __mn_hist)",
        "    delocal int e = 0",
        "",
        f"procedure __mn_pool_store(int slot, int val, int __mn_mem[], {TAPE_PARAMS}, {h})",
        f"    if slot < {cap} then",
        "        local int t = 0",
        "            t += __mn_mem[slot]",
        "            __mn_mem[slot] -= t",
        "            push(t, __mn_hist)",
        "        delocal int t = 0",
        "        __mn_mem[slot] += val",
        "    else",
        *tape_branch(["        push(v, __mn_hist)", "        v += val"]),
        f"    fi slot < {cap}",
        "",
        f"procedure __mn_pool_load(int slot, int __mn_mem[], int out, {TAPE_PARAMS}, {h})",
        f"    if slot < {cap} then",
        "        local int t = 0",
        "            t += __mn_mem[slot]",
        "            push(out, __mn_hist)",
        "            out += t",
        "            push(t, __mn_hist)",
        "        delocal int t = 0",
        "    else",
        *tape_branch(["        push(out, __mn_hist)", "        out += v"]),
        f"    fi slot < {cap}",
        "",
    ]
    return "\n".join(lines)
