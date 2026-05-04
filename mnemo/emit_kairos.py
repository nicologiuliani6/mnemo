"""
Emissione minimale IR → sorgente Kairos.

v0: `main` con dichiarazioni `int` per le locals; altre procedure senza locals extra.
    Istruzioni non ancora mappate (copy, store_rev, branch) → commento TODO.
"""

from __future__ import annotations

from mnemo.ir import (
    Function,
    IAddEq,
    IBranch,
    ICall,
    IComment,
    IConst,
    ICopy,
    IFromUntilKairos,
    IHistPush,
    IIfKairos,
    IJump,
    ILabel,
    ILocalBlock,
    IPar,
    IReturn,
    ISrecv,
    ISsend,
    IShow,
    IStoreRev,
    ISubEq,
    ISwap,
    IXorEq,
    Instr,
    Operand,
    Program,
    operand_str,
)


def _emit_operand_for_expr(o: Operand) -> str:
    return operand_str(o)


def _emit_instr_seq(lines: list[str], instrs: list[Instr], indent: str) -> None:
    """
    Due IAddEq consecutivi sullo stesso `dst` (tipico di rhs `a + b` in _eval_expr)
    diventano un solo `dst += ((a) + (b))` così la VM non ha una finestra tra due letture
    di int condivisi nel PAR (Kairos → un solo PUSHEQ / resolve_expr parentesizzato).
    """
    i = 0
    while i < len(instrs):
        ins = instrs[i]
        if (
            isinstance(ins, IAddEq)
            and i + 1 < len(instrs)
            and isinstance(instrs[i + 1], IAddEq)
            and ins.dst == instrs[i + 1].dst
            and str(ins.dst).startswith("__mn_e")
        ):
            nxt = instrs[i + 1]
            # Una sola coppia di parentesi: `(a + b)` così resolve_expr legge lhs/rhs flat
            # (evita `( (a) + (b) )` dove gli atomi tra parentesi rompono il parser).
            lines.append(
                f"{indent}{ins.dst} += ({_emit_operand_for_expr(ins.rhs)}"
                f" + {_emit_operand_for_expr(nxt.rhs)})"
            )
            i += 2
            continue
        _emit_instr(lines, ins, indent)
        i += 1


def _emit_instr(lines: list[str], ins: Instr, indent: str) -> None:
    if isinstance(ins, IComment):
        lines.append(f"{indent}// {ins.text}")
        return
    if isinstance(ins, IConst):
        lines.append(f"{indent}{ins.dst} += {ins.value}")
        return
    if isinstance(ins, ICopy):
        lines.append(
            f"{indent}// IR copy {ins.dst} <- {ins.src} "
            f"(snap + add_eq o runtime; vedi mnemo/runtime)"
        )
        return
    if isinstance(ins, IAddEq):
        lines.append(f"{indent}{ins.dst} += {_emit_operand_for_expr(ins.rhs)}")
        return
    if isinstance(ins, ISubEq):
        lines.append(f"{indent}{ins.dst} -= {_emit_operand_for_expr(ins.rhs)}")
        return
    if isinstance(ins, IXorEq):
        lines.append(f"{indent}{ins.dst} ^= {_emit_operand_for_expr(ins.rhs)}")
        return
    if isinstance(ins, ISwap):
        lines.append(f"{indent}{ins.a} <=> {ins.b}")
        return
    if isinstance(ins, IHistPush):
        lines.append(f"{indent}push({ins.var}, {ins.hist})")
        return
    if isinstance(ins, IStoreRev):
        lines.append(
            f"{indent}// IR store_rev {ins.dst} <- {ins.src} hist={ins.hist} "
            f"(espansione: vedi examples/malloc.kairos mem_write)"
        )
        return
    if isinstance(ins, ICall):
        args = ", ".join(ins.args)
        lines.append(f"{indent}call {ins.proc}({args})")
        return
    if isinstance(ins, ILabel):
        lines.append(f"{indent}// label {ins.name}")
        return
    if isinstance(ins, IBranch):
        lines.append(
            f"{indent}// br {ins.lhs} {ins.op} {operand_str(ins.rhs)} "
            f"? {ins.then_label} : {ins.else_label}  → if/fi Kairos"
        )
        return
    if isinstance(ins, IJump):
        lines.append(f"{indent}// jmp {ins.label}")
        return
    if isinstance(ins, IReturn):
        lines.append(f"{indent}// return")
        return
    if isinstance(ins, IShow):
        if ins.as_char:
            lines.append(f"{indent}show({ins.var}, char)")
        else:
            lines.append(f"{indent}show({ins.var})")
        return
    if isinstance(ins, IIfKairos):
        rhs = ins.rhs
        lines.append(f"{indent}if {ins.lhs} {ins.op} {rhs} then")
        ind2 = indent + "    "
        _emit_instr_seq(lines, ins.then_instrs, ind2)
        if ins.else_instrs is not None:
            lines.append(f"{indent}else")
            _emit_instr_seq(lines, ins.else_instrs, ind2)
        lines.append(f"{indent}fi {ins.lhs} {ins.op} {rhs}")
        return
    if isinstance(ins, IFromUntilKairos):
        lines.append(
            f"{indent}from {ins.entry_lhs} {ins.entry_op} {ins.entry_rhs} loop"
        )
        ind2 = indent + "    "
        _emit_instr_seq(lines, ins.body_instrs, ind2)
        lines.append(
            f"{indent}until {ins.until_lhs} {ins.until_op} {ins.until_rhs}"
        )
        return
    if isinstance(ins, ILocalBlock):
        lines.append(f"{indent}local int {ins.var} = 0")
        ind2 = indent + "    "
        _emit_instr_seq(lines, ins.body_instrs, ind2)
        lines.append(f"{indent}delocal int {ins.var} = 0")
        return
    if isinstance(ins, ISsend):
        inner = ", ".join(ins.payload_atoms)
        lines.append(f"{indent}ssend(<{inner}>, {ins.channel})")
        return
    if isinstance(ins, ISrecv):
        inner = ", ".join(ins.dests)
        lines.append(f"{indent}srecv(<{inner}>, {ins.channel})")
        return
    if isinstance(ins, IPar):
        lines.append(f"{indent}par")
        br_ind = indent + "    "
        for i, branch in enumerate(ins.branches):
            if i > 0:
                lines.append(f"{indent}and")
            _emit_instr_seq(lines, branch, br_ind)
        lines.append(f"{indent}rap")
        return
    raise TypeError(ins)


def _is_unified_mem_local(name: str) -> bool:
    """
    Celle `__mn_memN` del registro globale Mnemo. La VM `push(v, hist)` azzera `v`;
    nelle procedure utente queste celle sono spesso alias dei parametri del chiamante,
    quindi l'epilogo non deve fare push sulla cella di ritorno (si usa `delocal int x x`).
    """

    if not name.startswith("__mn_mem"):
        return False
    suffix = name[8:]
    return bool(suffix) and suffix.isdigit()


def _emit_main(fn: Function) -> str:
    """
    Tutti gli interi di procedura: `local int … = 0`; in coda `push` (azzera) e `delocal int … = 0`.
    Le variabili solo per `continue` sono `__mn_lc*` (IR): non compaiono qui, solo nei blocchi
    `local`/`delocal` annidati — niente omonimia con `__mn_e*` in testa al main.
    """
    lines: list[str] = ["procedure main()"]
    stacks = [(t, n) for t, n in fn.locals if t == "stack"]
    stack_names = {n for _t, n in stacks}
    channels = [(t, n) for t, n in fn.locals if t == "channel"]
    ints = [(t, n) for t, n in fn.locals if t == "int"]
    hist = "__mn_hist"

    need_stack_line = (len(ints) > 0 or len(channels) > 0) and hist not in stack_names
    if need_stack_line:
        lines.append(f"    stack {hist}")
    for typ, name in stacks:
        lines.append(f"    stack {name}")

    if len(ints) > 0 or len(channels) > 0:
        for _t, name in channels:
            lines.append(f"    local channel {name} = empty")
        for _t, name in ints:
            lines.append(f"    local int {name} = 0")
        body_indent = "        "
    else:
        body_indent = "    "

    for b in fn.blocks:
        _emit_instr_seq(lines, b.instrs, body_indent)

    for _t, name in reversed(ints):
        lines.append(f"    push({name}, {hist})")
        lines.append(f"    delocal int {name} = 0")
    for _t, name in reversed(channels):
        lines.append(f"    delocal channel {name} = empty")

    return "\n".join(lines)


def _emit_procedure(fn: Function) -> str:
    """
    Integer locals: `local int … = 0` (non `int …` a livello procedura: `DECL` →
    NULL in VM, `+=` / PUSHEQ falliscono). Chiusura: `push` azzera prima di
    `delocal int … = 0` (la VM rifiuta LOCAL aperte a END_PROC).

    Per `__mn_memN`: niente `push` (non azzerare valori visti dal chiamante);
    `delocal int x x` — il valore atteso è letto da `x` e coincide col corrente.
    """
    param_parts: list[str] = []
    for typ, name in fn.params:
        if typ == "channel":
            param_parts.append(f"channel {name}")
        else:
            param_parts.append(f"int {name}")
    params = ", ".join(param_parts)
    lines: list[str] = [f"procedure {fn.name}({params})"]
    stacks = [(t, n) for t, n in fn.locals if t == "stack"]
    stack_names = {n for _t, n in stacks}
    channels = [(t, n) for t, n in fn.locals if t == "channel"]
    ints = [(t, n) for t, n in fn.locals if t == "int"]
    hist = "__mn_hist"

    need_stack_line = (len(ints) > 0 or len(channels) > 0) and hist not in stack_names
    if need_stack_line:
        lines.append(f"    stack {hist}")
    for _typ, name in stacks:
        lines.append(f"    stack {name}")

    if len(ints) > 0 or len(channels) > 0:
        for _t, name in channels:
            lines.append(f"    local channel {name} = empty")
        for _t, name in ints:
            lines.append(f"    local int {name} = 0")
        body_indent = "        "
    else:
        body_indent = "    "

    for b in fn.blocks:
        _emit_instr_seq(lines, b.instrs, body_indent)

    for _t, name in reversed(ints):
        if _is_unified_mem_local(name):
            lines.append(f"    delocal int {name} {name}")
        else:
            lines.append(f"    push({name}, {hist})")
            lines.append(f"    delocal int {name} = 0")
    for _t, name in reversed(channels):
        lines.append(f"    delocal channel {name} = empty")

    return "\n".join(lines)


def emit_program(p: Program) -> str:
    chunks: list[str] = []
    for fn in p.functions:
        if fn.name == "main":
            chunks.append(_emit_main(fn))
        else:
            chunks.append(_emit_procedure(fn))
    return "\n".join(chunks).rstrip() + "\n"
