"""
Emissione del sorgente Kairos per `__mn_pool_*` con N celle (`__mn_mem0` … `__mn_mem{N-1}`).

Kairos non ha array di int da passare per nome al chiamante: le celle sono parametri espliciti
e il dispatcher `if slot == k` è generato in Python in base a N (compile-time).

Quando N è grande, una singola procedura supera i limiti della VM sui parametri / argomenti
di `call`: si emettono slice (`__mn_pool_*_b0`, …) e il lowering IR dispatcha con divmod.
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
    """Procedure heap dinamico: slot >= heap_base → `vm->mn_pool[slot]` via ops
    VM POOLPUSH/POOLADD/POOLGET (indice runtime, pool cresce on-demand). Guardia
    `if slot >= heap_base` → no-op per gli slot statici (serviti dal dispatch
    `if slot==k`); mutuamente esclusive, quindi store/load chiamano entrambe."""
    hb = heap_base
    return "\n".join(
        [
            f"// Heap dinamico (vm->mn_pool): slot >= {hb} (heap malloc, no alias nominato).",
            "// Cresce on-demand → niente --ptr-pool-size per malloc-in-loop runtime.",
            "procedure __mn_pool_store_dyn(int slot, int val, stack __mn_hist, stack __mn_scratch)",
            f"    if slot >= {hb} then",
            "        poolpush(slot, __mn_hist)",
            "        pooladd(slot, val)",
            f"    fi slot >= {hb}",
            "",
            "procedure __mn_pool_load_dyn(int slot, int out, stack __mn_hist, stack __mn_scratch)",
            f"    if slot >= {hb} then",
            "        local int t = 0",
            "            poolget(slot, t)",
            "            push(out, __mn_hist)",
            "            out += t",
            "            push(t, __mn_hist)",
            "        delocal int t = 0",
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
        "",
        _pool_alloc_free_src(),
        f"procedure __mn_pool_store(int slot, int val, {mem_params}, stack __mn_hist, stack __mn_scratch)",
    ]

    for i in range(n):
        lines.extend(
            [
                f"    if slot == {i} then",
                f"        push(__mn_mem{i}, __mn_hist)",
                f"        __mn_mem{i} += val",
                f"    fi slot == {i}",
            ]
        )

    lines.extend(
        [
            "",
            f"procedure __mn_pool_load(int slot, {mem_params}, int out, stack __mn_hist, stack __mn_scratch)",
        ]
    )

    for i in range(n):
        lines.extend(
            [
                f"    if slot == {i} then",
                "        local int t = 0",
                f"            t += __mn_mem{i}",
                "            push(out, __mn_hist)",
                "            out += t",
                "            push(t, __mn_hist)",
                "        delocal int t = 0",
                f"    fi slot == {i}",
            ]
        )

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
