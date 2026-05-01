"""Stampa testuale dell'IR Mnemo (per test e debug)."""

from __future__ import annotations

from mnemo.ir import (
    Block,
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
    ILocalBlock,
    IJump,
    ILabel,
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


def _dump_instr(i: Instr, prefix: str = "") -> str:
    if isinstance(i, IComment):
        return f"{prefix}  // {i.text}"
    if isinstance(i, IConst):
        return f"{prefix}  const {i.dst} = {i.value}"
    if isinstance(i, ICopy):
        return f"{prefix}  copy {i.dst} <- {i.src}"
    if isinstance(i, IAddEq):
        return f"{prefix}  add_eq {i.dst} += {operand_str(i.rhs)}"
    if isinstance(i, ISubEq):
        return f"{prefix}  sub_eq {i.dst} -= {operand_str(i.rhs)}"
    if isinstance(i, IXorEq):
        return f"{prefix}  xor_eq {i.dst} ^= {operand_str(i.rhs)}"
    if isinstance(i, ISwap):
        return f"{prefix}  swap {i.a} <=> {i.b}"
    if isinstance(i, IHistPush):
        return f"{prefix}  hist_push {i.hist} <- {i.var}"
    if isinstance(i, IStoreRev):
        return f"{prefix}  store_rev {i.dst} <- {i.src}  (hist {i.hist})"
    if isinstance(i, ICall):
        args = ", ".join(i.args)
        return f"{prefix}  call {i.proc}({args})"
    if isinstance(i, ILabel):
        return f"{prefix}{i.name}:"
    if isinstance(i, IBranch):
        r = operand_str(i.rhs)
        return f"{prefix}  br {i.lhs} {i.op} {r} ? {i.then_label} : {i.else_label}"
    if isinstance(i, IJump):
        return f"{prefix}  jmp {i.label}"
    if isinstance(i, IReturn):
        return f"{prefix}  return"
    if isinstance(i, IIfKairos):
        lines = [f"{prefix}  if_kairos {i.lhs} {i.op} {i.rhs}"]
        p2 = prefix + "    "
        for sub in i.then_instrs:
            lines.append(_dump_instr(sub, p2))
        if i.else_instrs:
            lines.append(f"{prefix}  else")
            for sub in i.else_instrs:
                lines.append(_dump_instr(sub, p2))
        return "\n".join(lines)
    if isinstance(i, IFromUntilKairos):
        lines = [
            f"{prefix}  from_until entry {i.entry_lhs} {i.entry_op} {i.entry_rhs}"
        ]
        p2 = prefix + "    "
        for sub in i.body_instrs:
            lines.append(_dump_instr(sub, p2))
        lines.append(
            f"{prefix}  until {i.until_lhs} {i.until_op} {i.until_rhs}"
        )
        return "\n".join(lines)
    if isinstance(i, ILocalBlock):
        lines = [f"{prefix}  local_block {i.var}"]
        p2 = prefix + "    "
        for sub in i.body_instrs:
            lines.append(_dump_instr(sub, p2))
        return "\n".join(lines)
    raise TypeError(f"istruzione IR sconosciuta: {type(i)}")


def dump_block(b: Block) -> str:
    lines = [f"block {b.bid} {{"]
    for ins in b.instrs:
        lines.append(_dump_instr(ins))
    lines.append("}")
    return "\n".join(lines)


def dump_function(f: Function) -> str:
    pl = ", ".join(f"{t} {n}" for t, n in f.params)
    ll = ", ".join(f"{t} {n}" for t, n in f.locals) if f.locals else ""
    head = f"fn {f.name}({pl})"
    if ll:
        head += f" locals [{ll}]"
    lines = [head + " {"]
    for b in f.blocks:
        for line in dump_block(b).splitlines():
            lines.append("  " + line)
    lines.append("}")
    return "\n".join(lines)


def dump_program(p: Program) -> str:
    return "\n\n".join(dump_function(fn) for fn in p.functions)


def dump_operand(o: Operand) -> str:
    return operand_str(o)
