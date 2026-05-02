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
    IReturn,
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
        lines.append(f"{indent}show({ins.var})")
        return
    if isinstance(ins, IIfKairos):
        rhs = ins.rhs
        lines.append(f"{indent}if {ins.lhs} {ins.op} {rhs} then")
        ind2 = indent + "    "
        for sub in ins.then_instrs:
            _emit_instr(lines, sub, ind2)
        if ins.else_instrs is not None:
            lines.append(f"{indent}else")
            for sub in ins.else_instrs:
                _emit_instr(lines, sub, ind2)
        lines.append(f"{indent}fi {ins.lhs} {ins.op} {rhs}")
        return
    if isinstance(ins, IFromUntilKairos):
        lines.append(
            f"{indent}from {ins.entry_lhs} {ins.entry_op} {ins.entry_rhs} loop"
        )
        ind2 = indent + "    "
        for sub in ins.body_instrs:
            _emit_instr(lines, sub, ind2)
        lines.append(
            f"{indent}until {ins.until_lhs} {ins.until_op} {ins.until_rhs}"
        )
        return
    if isinstance(ins, ILocalBlock):
        lines.append(f"{indent}local int {ins.var} = 0")
        ind2 = indent + "    "
        for sub in ins.body_instrs:
            _emit_instr(lines, sub, ind2)
        lines.append(f"{indent}delocal int {ins.var} = 0")
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
    ints = [(t, n) for t, n in fn.locals if t == "int"]
    hist = "__mn_hist"

    if len(ints) > 0 and hist not in stack_names:
        lines.append(f"    stack {hist}")
    for typ, name in stacks:
        lines.append(f"    stack {name}")

    if len(ints) > 0:
        for _t, name in ints:
            lines.append(f"    local int {name} = 0")
        body_indent = "        "
    else:
        body_indent = "    "

    for b in fn.blocks:
        for ins in b.instrs:
            _emit_instr(lines, ins, body_indent)

    for _t, name in reversed(ints):
        lines.append(f"    push({name}, {hist})")
        lines.append(f"    delocal int {name} = 0")

    return "\n".join(lines)


def _emit_procedure(fn: Function) -> str:
    """
    Integer locals: `local int … = 0` (non `int …` a livello procedura: `DECL` →
    NULL in VM, `+=` / PUSHEQ falliscono). Chiusura: `push` azzera prima di
    `delocal int … = 0` (la VM rifiuta LOCAL aperte a END_PROC).

    Per `__mn_memN`: niente `push` (non azzerare valori visti dal chiamante);
    `delocal int x x` — il valore atteso è letto da `x` e coincide col corrente.
    """
    params = ", ".join(f"int {name}" for _t, name in fn.params)
    lines: list[str] = [f"procedure {fn.name}({params})"]
    stacks = [(t, n) for t, n in fn.locals if t == "stack"]
    stack_names = {n for _t, n in stacks}
    ints = [(t, n) for t, n in fn.locals if t == "int"]
    hist = "__mn_hist"

    if len(ints) > 0 and hist not in stack_names:
        lines.append(f"    stack {hist}")
    for _typ, name in stacks:
        lines.append(f"    stack {name}")

    if len(ints) > 0:
        for _t, name in ints:
            lines.append(f"    local int {name} = 0")
        body_indent = "        "
    else:
        body_indent = "    "

    for b in fn.blocks:
        for ins in b.instrs:
            _emit_instr(lines, ins, body_indent)

    for _t, name in reversed(ints):
        if _is_unified_mem_local(name):
            lines.append(f"    delocal int {name} {name}")
        else:
            lines.append(f"    push({name}, {hist})")
            lines.append(f"    delocal int {name} = 0")

    return "\n".join(lines)


def emit_program(p: Program) -> str:
    chunks: list[str] = []
    for fn in p.functions:
        if fn.name == "main":
            chunks.append(_emit_main(fn))
        else:
            chunks.append(_emit_procedure(fn))
    return "\n".join(chunks).rstrip() + "\n"
