"""
Emissione minimale IR → sorgente Kairos.

v0: `main` con dichiarazioni `int` per le locals; altre procedure senza locals extra.
    Istruzioni non ancora mappate (copy, store_rev, branch) → commento TODO.
"""

from __future__ import annotations

from mnemo.kairos_reserved import kairos_escape_id
from mnemo.ir import (
    Function,
    Imm,
    IAddEq,
    IBranch,
    ICall,
    IUncall,
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
    ITry,
    IVmDump,
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
    Due IAddEq consecutivi sullo stesso `dst` possono fondersi in `dst += (a + b)` solo
    se **entrambi** gli addendi sono costanti (`Imm`). Se uno è una `Var` (es. risultato di
    `pool_load` o altra lettura), `dst += (v1 + v2)` in Kairos non replica due `+=` separati
    e rompe espressioni come `*p + *q`.
    Con due sole costanti, `(k1 + k2)` è puramente aritmetico e resta sicuro.
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
            and isinstance(ins.rhs, Imm)
            and isinstance(instrs[i + 1].rhs, Imm)
            and ins.rhs.value >= 0
            and instrs[i + 1].rhs.value >= 0
        ):
            nxt = instrs[i + 1]
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
        if ins.value < 0:
            # Kairos parser rifiuta letterali negativi (`+= -1` → token non atteso).
            # Equivalente reversibile: `dst -= N`.
            lines.append(f"{indent}{ins.dst} -= {-ins.value}")
        else:
            lines.append(f"{indent}{ins.dst} += {ins.value}")
        return
    if isinstance(ins, ICopy):
        lines.append(
            f"{indent}// IR copy {ins.dst} <- {ins.src} "
            f"(snap + add_eq o runtime; vedi mnemo/runtime)"
        )
        return
    if isinstance(ins, IAddEq):
        if isinstance(ins.rhs, Imm) and ins.rhs.value < 0:
            lines.append(f"{indent}{ins.dst} -= {-ins.rhs.value}")
        else:
            lines.append(f"{indent}{ins.dst} += {_emit_operand_for_expr(ins.rhs)}")
        return
    if isinstance(ins, ISubEq):
        if isinstance(ins.rhs, Imm) and ins.rhs.value < 0:
            lines.append(f"{indent}{ins.dst} += {-ins.rhs.value}")
        else:
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
        pname = kairos_escape_id(ins.proc)
        lines.append(f"{indent}call {pname}({args})")
        return
    if isinstance(ins, IUncall):
        args = ", ".join(ins.args)
        pname = kairos_escape_id(ins.proc)
        lines.append(f"{indent}uncall {pname}({args})")
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
    if isinstance(ins, IVmDump):
        lines.append(f"{indent}dump()")
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
            f"{indent}from {ins.entry_lhs} {ins.entry_op} {ins.entry_rhs} do"
        )
        ind2 = indent + "    "
        _emit_instr_seq(lines, ins.body_instrs, ind2)
        until = f"until {ins.until_lhs} {ins.until_op} {ins.until_rhs}"
        if ins.body2_instrs:
            lines.append(f"{indent}loop")
            _emit_instr_seq(lines, ins.body2_instrs, ind2)
            lines.append(f"{indent}{until}")
        else:
            # `loop` sulla stessa riga di `until`: il conteggio righe resta
            # identico alla forma a un corpo, e con esso i tag @line del
            # bytecode su cui si basa l'inverter della VM.
            lines.append(f"{indent}loop {until}")
        return
    if isinstance(ins, ITry):
        cond = f"{ins.lhs} {ins.op} {ins.rhs}"
        lines.append(f"{indent}try {cond}")
        ind2 = indent + "    "
        _emit_instr_seq(lines, ins.body_instrs, ind2)
        if ins.rollback_instrs is not None:
            lines.append(f"{indent}rollback")
            _emit_instr_seq(lines, ins.rollback_instrs, ind2)
        lines.append(f"{indent}yrt {cond}")
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


def _stack_names_from_fn(fn: Function) -> set[str]:
    return {n for t, n in fn.locals if t == "stack"} | {
        n for t, n in fn.params if t == "stack"
    }


def _emit_main(fn: Function) -> str:
    """
    Tutti gli interi di procedura: `local int … = 0`; in coda `push` (azzera) e `delocal int … = 0`.
    Le variabili solo per `continue` sono `__mn_lc*` (IR): non compaiono qui, solo nei blocchi
    `local`/`delocal` annidati — niente omonimia con `__mn_e*` in testa al main.
    """
    lines: list[str] = ["procedure main()"]
    stacks = [(t, n) for t, n in fn.locals if t == "stack"]
    stack_names = _stack_names_from_fn(fn)
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

    I parametri formali (inclusi `__mn_mem*`) non stanno in `fn.locals`: l'epilogo
    riguarda solo i `local int` del corpo. Anche le celle `__mn_mem*` extra (es.
    seconda partizione per `par`) usano la stessa forma `push` + `delocal … = 0`
    accettata dal parser Kairos.
    """
    param_parts: list[str] = []
    for typ, name in fn.params:
        if typ == "channel":
            param_parts.append(f"channel {name}")
        elif typ == "stack":
            param_parts.append(f"stack {name}")
        else:
            param_parts.append(f"int {name}")
    params = ", ".join(param_parts)
    pname = kairos_escape_id(fn.name)
    lines: list[str] = [f"procedure {pname}({params})"]
    stacks = [(t, n) for t, n in fn.locals if t == "stack"]
    stack_names = _stack_names_from_fn(fn)
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
