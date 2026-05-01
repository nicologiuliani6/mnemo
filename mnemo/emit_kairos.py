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


def _emit_main(fn: Function) -> str:
    lines: list[str] = ["procedure main()"]
    for typ, name in fn.locals:
        if typ == "stack":
            lines.append(f"    stack {name}")
        else:
            lines.append(f"    int {name}")
    for b in fn.blocks:
        for ins in b.instrs:
            _emit_instr(lines, ins, "    ")
    return "\n".join(lines)


def _emit_procedure(fn: Function) -> str:
    params = ", ".join(f"int {name}" for _t, name in fn.params)
    lines: list[str] = [f"procedure {fn.name}({params})"]
    for typ, name in fn.locals:
        if typ == "stack":
            lines.append(f"    stack {name}")
        else:
            lines.append(f"    int {name}")
    for b in fn.blocks:
        for ins in b.instrs:
            _emit_instr(lines, ins, "    ")
    return "\n".join(lines)


def emit_program(p: Program) -> str:
    chunks: list[str] = []
    for fn in p.functions:
        if fn.name == "main":
            chunks.append(_emit_main(fn))
        else:
            chunks.append(_emit_procedure(fn))
    return "\n".join(chunks).rstrip() + "\n"
