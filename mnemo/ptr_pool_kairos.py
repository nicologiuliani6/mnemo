"""
Emissione del sorgente Kairos per `__mn_pool_*` con N celle (`__mn_mem0` … `__mn_mem{N-1}`).

Kairos non ha array di int da passare per nome al chiamante: le celle sono parametri espliciti
e il dispatcher `if slot == k` è generato in Python in base a N (compile-time).

Quando N è grande, una singola procedura supera i limiti della VM sui parametri / argomenti
di `call`: si emettono slice (`__mn_pool_*_b0`, …) e il lowering IR dispatcha con divmod.

Due livelli, entrambi 100% Kairos puro (nessun opcode VM nativo — vedi
kairos_sos.tex, σ:Var⇀ℤ∪ℤ*∪Chan, POOLPUSH/POOLADD/POOLGET erano un'estensione
VM fuori da questa spec, rimossa): il dispatch STATICO (`if slot==k`, celle
nominate __mn_mem*, dimensione = celle nominate del programma, calcolata da
`layout_collect.py`) copre la stragrande maggioranza degli accessi (qualunque
slot con alias nominato — array/struct/scalari). Lo heap DINAMICO
(`_emit_dynamic_pool_procs`, sotto) copre gli slot `>= heap_base` (malloc,
senza alias nominato: size non costante o allocazioni in un loop a
trip-count runtime) — non più un array C nativo cresciuto on-demand, ma una
struttura associativa (indirizzo,valore) costruita sopra uno `stack` Kairos
con scansione lineare O(n) per get/set. Con `heap_base=None` il modello
dinamico è disattivato del tutto (compat legacy): non è il path usato da
`compile.py`, che passa sempre un `heap_base` esplicito quando il programma
usa il pool puntatori.
"""

from __future__ import annotations

import math

from mnemo.errors import MnemoCompileError
from mnemo.kairos_limits import MONOLITHIC_POOL_MEM_MAX, POOL_BANK_SIZE, PTR_POOL_MAX


def emit_ptr_pool_kairos(n: int, heap_base: int | None = None) -> str:
    """`n` = numero di celle statiche su cui fa dispatch `if slot==k` (la
    memoria nominata del programma: array stack, globali, struct — celle
    `__mn_mem0..n-1`). Gli slot >= `heap_base` (heap da malloc, senza alias
    nominato) sono serviti dalle procedure `__mn_pool_*_dyn` che indicizzano
    l'heap VM dinamico `vm->mn_pool` → crescita on-demand, niente
    `--ptr-pool-size`. Se `heap_base` è None il modello dinamico è disattivato
    (compat: solo dispatch statico sull'intero `n`)."""
    if n > PTR_POOL_MAX:
        raise MnemoCompileError(
            f"celle pool statiche {n} > max {PTR_POOL_MAX}"
        )
    if heap_base is None and n < 1:
        raise MnemoCompileError(
            f"ptr_pool_size deve essere tra 1 e {PTR_POOL_MAX}, non {n}"
        )
    static = ""
    if n >= 1:
        if n <= MONOLITHIC_POOL_MEM_MAX:
            static = _emit_monolithic_ptr_pool_kairos(n)
        else:
            static = _emit_banked_ptr_pool_kairos(n)
    if heap_base is None:
        return static
    dyn = _emit_dynamic_pool_procs(heap_base)
    if not static:
        return dyn
    return static.rstrip() + "\n\n" + dyn


def _emit_dynamic_pool_procs(heap_base: int) -> str:
    """Procedure heap dinamico, 100% Kairos puro: slot >= heap_base non ha una
    cella nominata (__mn_mem*), quindi vive su una struttura associativa
    costruita sopra uno `stack` Kairos (`__mn_pool_heap`, coppie
    indirizzo/valore) + un contatore `__mn_pool_heap_n` (int, threaded by-ref
    come `__mn_pool_ctr`) — non più sull'array C nativo `vm->mn_pool` (opcode
    POOLPUSH/POOLADD/POOLGET, rimossi: erano un'estensione VM fuori dalla
    spec pura σ:Var⇀ℤ∪ℤ*∪Chan). Store/load fanno scansione LINEARE O(n) sui
    record correnti (più lento del pool nativo, accettato per restare 100%
    puro — vedi commenti nelle singole procedure sotto)."""
    hb = heap_base
    return "\n".join(
        [
            "// Heap dinamico PURO (100% Kairos, nessun opcode nativo POOLPUSH/POOLADD/",
            f"// POOLGET): slot >= {hb} (heap malloc, no alias nominato). Sostituisce",
            "// `vm->mn_pool` (array C nativo cresciuto on-demand) con una struttura dati",
            "// costruita sopra uno `stack` Kairos — coppie (indirizzo, valore), 2 celle",
            "// stack per record — e scansione LINEARE O(n) per get/set (più lento del",
            "// pool nativo ma 100% puro, come da direttiva). `__mn_pool_heap_n` (int,",
            "// threaded by-ref come `__mn_pool_ctr`) conta i record correnti: serve",
            "// perché `from...until` in Kairos è un do-while (esegue il corpo almeno una",
            "// volta), quindi uno scan su heap vuoto (n=0) va evitato con un `if n>0`",
            "// esterno, altrimenti `pop` su stack vuoto è un errore runtime (Pop-Err).",
            "// Store: scansiona TUTTI gli n record (nessun early-exit — Kairos non ha",
            "// guardie booleane composte tipo `i==n || found==1`, solo confronti",
            "// singoli), drenando __mn_pool_heap in un temporaneo __mn_pool_tmp mentre",
            "// decodifica; se il record combacia, salva il vecchio valore su hist (come",
            "// POOLPUSH) e aggiunge `val` (come POOLADD); poi ripristina tutti i record",
            "// da __mn_pool_tmp a __mn_pool_heap (stesso ordine originale — pop/push",
            "// LIFO simmetrico). Se non trovato, appende un nuovo record (indirizzo,",
            "// val) e incrementa il contatore.",
            "// Load: stessa scansione, legge il valore SENZA azzerarlo (come POOLGET);",
            "// se non trovato, valore = 0 (heap \"zero-filled\" come l'array nativo).",
            f"procedure __mn_pool_store_dyn(int slot, int val, stack __mn_pool_heap, int __mn_pool_heap_n, stack __mn_hist, stack __mn_scratch)",
            f"    if slot >= {hb} then",
            "        local int found = 0",
            "        local stack __mn_pool_tmp = nil",
            "        if __mn_pool_heap_n > 0 then",
            "            local int i = 0",
            "            from i == 0 do",
            "                local int a_i = 0",
            "                local int v_i = 0",
            "                pop(v_i, __mn_pool_heap)",
            "                pop(a_i, __mn_pool_heap)",
            "                local int match = 0",
            "                if a_i == slot then",
            "                    match += 1",
            "                fi a_i == slot",
            "                if match == 1 then",
            "                    push(v_i, __mn_hist)",
            "                    v_i += val",
            "                    found += 1",
            "                fi match == 1",
            "                push(a_i, __mn_pool_tmp)",
            "                push(v_i, __mn_pool_tmp)",
            "                push(match, __mn_hist)",
            "                delocal int match = 0",
            "                delocal int v_i = 0",
            "                delocal int a_i = 0",
            "                i += 1",
            "            loop until i == __mn_pool_heap_n",
            "            local int j = 0",
            "            from j == 0 do",
            "                local int a_j = 0",
            "                local int v_j = 0",
            "                pop(v_j, __mn_pool_tmp)",
            "                pop(a_j, __mn_pool_tmp)",
            "                push(a_j, __mn_pool_heap)",
            "                push(v_j, __mn_pool_heap)",
            "                delocal int v_j = 0",
            "                delocal int a_j = 0",
            "                j += 1",
            "            loop until j == __mn_pool_heap_n",
            "            push(j, __mn_hist)",
            "            delocal int j = 0",
            "            push(i, __mn_hist)",
            "            delocal int i = 0",
            "        fi __mn_pool_heap_n > 0",
            "        delocal stack __mn_pool_tmp = nil",
            "        if found == 0 then",
            "            local int slot_copy = 0",
            "            slot_copy += slot",
            "            local int newval = 0",
            "            newval += val",
            "            push(slot_copy, __mn_pool_heap)",
            "            push(newval, __mn_pool_heap)",
            "            __mn_pool_heap_n += 1",
            "            push(newval, __mn_hist)",
            "            delocal int newval = 0",
            "            push(slot_copy, __mn_hist)",
            "            delocal int slot_copy = 0",
            "        fi found == 0",
            "        push(found, __mn_hist)",
            "        delocal int found = 0",
            f"    fi slot >= {hb}",
            "",
            f"procedure __mn_pool_load_dyn(int slot, int out, stack __mn_pool_heap, int __mn_pool_heap_n, stack __mn_hist, stack __mn_scratch)",
            f"    if slot >= {hb} then",
            "        local int found = 0",
            "        local int foundval = 0",
            "        local stack __mn_pool_tmp = nil",
            "        if __mn_pool_heap_n > 0 then",
            "            local int i = 0",
            "            from i == 0 do",
            "                local int a_i = 0",
            "                local int v_i = 0",
            "                pop(v_i, __mn_pool_heap)",
            "                pop(a_i, __mn_pool_heap)",
            "                local int match = 0",
            "                if a_i == slot then",
            "                    match += 1",
            "                fi a_i == slot",
            "                if match == 1 then",
            "                    foundval += v_i",
            "                    found += 1",
            "                fi match == 1",
            "                push(a_i, __mn_pool_tmp)",
            "                push(v_i, __mn_pool_tmp)",
            "                push(match, __mn_hist)",
            "                delocal int match = 0",
            "                delocal int v_i = 0",
            "                delocal int a_i = 0",
            "                i += 1",
            "            loop until i == __mn_pool_heap_n",
            "            local int j = 0",
            "            from j == 0 do",
            "                local int a_j = 0",
            "                local int v_j = 0",
            "                pop(v_j, __mn_pool_tmp)",
            "                pop(a_j, __mn_pool_tmp)",
            "                push(a_j, __mn_pool_heap)",
            "                push(v_j, __mn_pool_heap)",
            "                delocal int v_j = 0",
            "                delocal int a_j = 0",
            "                j += 1",
            "            loop until j == __mn_pool_heap_n",
            "            push(j, __mn_hist)",
            "            delocal int j = 0",
            "            push(i, __mn_hist)",
            "            delocal int i = 0",
            "        fi __mn_pool_heap_n > 0",
            "        delocal stack __mn_pool_tmp = nil",
            "        push(out, __mn_hist)",
            "        out += foundval",
            "        push(foundval, __mn_hist)",
            "        delocal int foundval = 0",
            "        push(found, __mn_hist)",
            "        delocal int found = 0",
            f"    fi slot >= {hb}",
            "",
        ]
    ).rstrip() + "\n"


def _pool_alloc_free_src() -> str:
    """`__mn_pool_alloc`/`__mn_pool_free` — toccano solo `ctr` (l'header per-blocco
    è gestito dal lowering via store/load), quindi sono identici per pool
    monolitico e bancato. NB: op_push azzera la sorgente → mai `push(x)` prima di
    `x ±= …` su x stesso. `ctr -= nblk; ctr -= 1` è reversibile (inverse +=)."""
    return "\n".join(
        [
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
        ]
    )


def _emit_monolithic_ptr_pool_kairos(n: int) -> str:
    mem_params = ", ".join(f"int __mn_mem{i}" for i in range(n))

    # Modello block-aware con HEADER. Ogni malloc di nblk celle occupa nblk+1
    # celle a partire da `ctr`: mem{ctr}=nblk (header), mem{ctr+1..ctr+nblk}=dati;
    # il puntatore utente restituito è ctr+1. `ctr += nblk+1` → malloc concorrenti
    # non si sovrappongono. L'header è scritto/riletto dal LOWERING via
    # `__mn_pool_store`/`__mn_pool_load` (già banked-aware; lo store azzera la
    # cella col push, quindi l'header si auto-resetta al riuso). `alloc`/`free`
    # toccano solo `ctr`, quindi sono identici per pool monolitico e bancato.
    lines: list[str] = [
        f"// Pool puntatori Mnemo — generato, N={n} celle (__mn_mem0..__mn_mem{n - 1}).",
        "// Header per-blocco (scritto dal lowering): mem{ctr}=nblk; ptr=ctr+1.",
        "// Dispatch slot→cella via BINARY SEARCH (`if slot < mid`): O(log N) per",
        "// accesso invece che O(N) lineare → deref a indice runtime molto più veloce.",
        "",
        _pool_alloc_free_src(),
        f"procedure __mn_pool_store(int slot, int val, {mem_params}, stack __mn_hist, stack __mn_scratch)",
    ]

    def _store_leaf(i: int, ind: str) -> list[str]:
        return [
            f"{ind}push(__mn_mem{i}, __mn_hist)",
            f"{ind}__mn_mem{i} += val",
        ]

    def _load_leaf(i: int, ind: str) -> list[str]:
        return [
            f"{ind}local int t = 0",
            f"{ind}    t += __mn_mem{i}",
            f"{ind}    push(out, __mn_hist)",
            f"{ind}    out += t",
            f"{ind}    push(t, __mn_hist)",
            f"{ind}delocal int t = 0",
        ]

    def _tree(lo: int, hi: int, leaf, depth: int) -> list[str]:
        # Emette il dispatch per gli slot in [lo, hi): foglia = singola cella;
        # interno = `if slot < mid then <[lo,mid)> else <[mid,hi)> fi slot < mid`.
        ind = "    " * (depth + 1)
        if hi - lo == 1:
            return leaf(lo, ind)
        mid = (lo + hi) // 2
        out_l: list[str] = [f"{ind}if slot < {mid} then"]
        out_l += _tree(lo, mid, leaf, depth + 1)
        out_l.append(f"{ind}else")
        out_l += _tree(mid, hi, leaf, depth + 1)
        out_l.append(f"{ind}fi slot < {mid}")
        return out_l

    if n > 0:
        lines += _tree(0, n, _store_leaf, 0)

    lines += [
        "",
        f"procedure __mn_pool_load(int slot, {mem_params}, int out, stack __mn_hist, stack __mn_scratch)",
    ]
    if n > 0:
        lines += _tree(0, n, _load_leaf, 0)

    # alloc/free sono già emessi da _pool_alloc_free_src() in testa (mem-free).
    return "\n".join(lines).rstrip() + "\n"


def _emit_banked_ptr_pool_kairos(n: int) -> str:
    bsz = POOL_BANK_SIZE
    n_banks = math.ceil(n / bsz)
    lines: list[str] = [
        f"// Pool puntatori Mnemo — generato (bancato), N={n}, bank={bsz}, n_banks={n_banks}.",
        "// Limite VM su argomenti di call / parametri di procedura.",
        "// alloc/free mem-free (header gestito dal lowering via store/load bancati).",
        "",
        _pool_alloc_free_src(),
    ]

    for bi in range(n_banks):
        start = bi * bsz
        end = min(n, start + bsz)
        mem_params = ", ".join(f"int __mn_mem{i}" for i in range(start, end))
        lines.append(
            f"procedure __mn_pool_store_b{bi}(int lslot, int val, {mem_params}, stack __mn_hist, stack __mn_scratch)"
        )
        for j in range(start, end):
            rel = j - start
            lines.extend(
                [
                    f"    if lslot == {rel} then",
                    f"        push(__mn_mem{j}, __mn_hist)",
                    f"        __mn_mem{j} += val",
                    f"    fi lslot == {rel}",
                ]
            )
        lines.append("")

    for bi in range(n_banks):
        start = bi * bsz
        end = min(n, start + bsz)
        mem_params = ", ".join(f"int __mn_mem{i}" for i in range(start, end))
        lines.append(
            f"procedure __mn_pool_load_b{bi}(int lslot, {mem_params}, int out, stack __mn_hist, stack __mn_scratch)"
        )
        for j in range(start, end):
            rel = j - start
            lines.extend(
                [
                    f"    if lslot == {rel} then",
                    "        local int t = 0",
                    f"            t += __mn_mem{j}",
                    "            push(out, __mn_hist)",
                    "            out += t",
                    "            push(t, __mn_hist)",
                    "        delocal int t = 0",
                    f"    fi lslot == {rel}",
                ]
            )
        lines.append("")

    # free è mem-free (single proc da _pool_alloc_free_src, emesso in testa):
    # tocca solo `ctr`, niente dispatch per banca.
    return "\n".join(lines).rstrip() + "\n"
