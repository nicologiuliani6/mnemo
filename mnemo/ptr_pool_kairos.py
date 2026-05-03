"""
Emissione del sorgente Kairos per `__mn_pool_*` con N celle (`__mn_mem0` … `__mn_mem{N-1}`).

Kairos non ha array di int da passare per nome al chiamante: le celle sono parametri espliciti
e il dispatcher `if slot == k` è generato in Python in base a N (compile-time).
"""

from __future__ import annotations

from mnemo.errors import MnemoCompileError

PTR_POOL_MAX = 2048


def emit_ptr_pool_kairos(n: int) -> str:
    if n < 1 or n > PTR_POOL_MAX:
        raise MnemoCompileError(
            f"ptr_pool_size deve essere tra 1 e {PTR_POOL_MAX}, non {n}"
        )

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
