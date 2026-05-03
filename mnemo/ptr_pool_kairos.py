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


def emit_ptr_pool_kairos(n: int) -> str:
    if n < 1 or n > PTR_POOL_MAX:
        raise MnemoCompileError(
            f"ptr_pool_size deve essere tra 1 e {PTR_POOL_MAX}, non {n}"
        )
    if n <= MONOLITHIC_POOL_MEM_MAX:
        return _emit_monolithic_ptr_pool_kairos(n)
    return _emit_banked_ptr_pool_kairos(n)


def _emit_monolithic_ptr_pool_kairos(n: int) -> str:
    mem_params = ", ".join(f"int __mn_mem{i}" for i in range(n))

    lines: list[str] = [
        f"// Pool puntatori Mnemo — generato, N={n} celle (__mn_mem0..__mn_mem{n - 1}).",
        "// `__mn_pool_free`: azzera cella; se slot è l’ultima alloc (LIFO), dec ctr.",
        "",
        "procedure __mn_pool_alloc(int ctr, int out_slot)",
        "    stack __mn_hist",
        "    local int t = 0",
        "        t += ctr",
        "        push(ctr, __mn_hist)",
        "        ctr += 1",
        "        push(out_slot, __mn_hist)",
        "        out_slot += t",
        "        push(t, __mn_hist)",
        "    delocal int t = 0",
        "",
        f"procedure __mn_pool_store(int slot, int val, {mem_params})",
        "    stack __mn_hist",
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
            f"procedure __mn_pool_load(int slot, {mem_params}, int out)",
            "    stack __mn_hist",
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

    lines.extend(
        [
            "",
            f"procedure __mn_pool_free(int slot, {mem_params}, int ctr)",
            "    stack __mn_hist",
            "    local int ctr0 = 0",
            "        ctr0 += ctr",
        ]
    )

    for i in range(n):
        lines.extend(
            [
                f"        if slot == {i} then",
                f"            push(__mn_mem{i}, __mn_hist)",
                f"        fi slot == {i}",
            ]
        )

    for i in range(n):
        need = i + 1
        lines.extend(
            [
                f"        if slot == {i} then",
                f"            if ctr0 == {need} then",
                "                push(ctr, __mn_hist)",
                "                ctr -= 1",
                f"            fi ctr0 == {need}",
                f"        fi slot == {i}",
            ]
        )

    lines.extend(
        [
            "        push(ctr0, __mn_hist)",
            "    delocal int ctr0 = 0",
            "",
        ]
    )

    return "\n".join(lines).rstrip() + "\n"


def _emit_banked_ptr_pool_kairos(n: int) -> str:
    bsz = POOL_BANK_SIZE
    n_banks = math.ceil(n / bsz)
    lines: list[str] = [
        f"// Pool puntatori Mnemo — generato (bancato), N={n}, bank={bsz}, n_banks={n_banks}.",
        "// Limite VM su argomenti di call / parametri di procedura.",
        "",
        "procedure __mn_pool_alloc(int ctr, int out_slot)",
        "    stack __mn_hist",
        "    local int t = 0",
        "        t += ctr",
        "        push(ctr, __mn_hist)",
        "        ctr += 1",
        "        push(out_slot, __mn_hist)",
        "        out_slot += t",
        "        push(t, __mn_hist)",
        "    delocal int t = 0",
        "",
    ]

    for bi in range(n_banks):
        start = bi * bsz
        end = min(n, start + bsz)
        mem_params = ", ".join(f"int __mn_mem{i}" for i in range(start, end))
        lines.append(f"procedure __mn_pool_store_b{bi}(int lslot, int val, {mem_params})")
        lines.append("    stack __mn_hist")
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
        lines.append(f"procedure __mn_pool_load_b{bi}(int lslot, {mem_params}, int out)")
        lines.append("    stack __mn_hist")
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

    for bi in range(n_banks):
        start = bi * bsz
        end = min(n, start + bsz)
        mem_params = ", ".join(f"int __mn_mem{i}" for i in range(start, end))
        lines.append(f"procedure __mn_pool_free_b{bi}(int lslot, {mem_params}, int ctr)")
        lines.append("    stack __mn_hist")
        lines.append("    local int ctr0 = 0")
        lines.append("        ctr0 += ctr")
        for j in range(start, end):
            rel = j - start
            lines.extend(
                [
                    f"        if lslot == {rel} then",
                    f"            push(__mn_mem{j}, __mn_hist)",
                    f"        fi lslot == {rel}",
                ]
            )
        for j in range(start, end):
            rel = j - start
            need = j + 1
            lines.extend(
                [
                    f"        if lslot == {rel} then",
                    f"            if ctr0 == {need} then",
                    "                push(ctr, __mn_hist)",
                    "                ctr -= 1",
                    f"            fi ctr0 == {need}",
                    f"        fi lslot == {rel}",
                ]
            )
        lines.extend(
            [
                "        push(ctr0, __mn_hist)",
                "    delocal int ctr0 = 0",
                "",
            ]
        )

    return "\n".join(lines).rstrip() + "\n"
