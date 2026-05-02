"""
IR Mnemo — rappresentazione intermedia tra AST (C/Mnemo) e Kairos.

Design:
- Operandi: Imm (letterale) o Var (nome Kairos-friendly, es. __m_t0).
- Istruzioni esplicite per aritmetica in-place e per storia (store_rev, hist_push).
- Controllo: label, branch condizionale su (lhs, op, rhs) con confronti == != < <= > >=.
- Una Function ha blocchi; ogni Block ha una lista ordinata di istruzioni.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Union

# --- Operand ---------------------------------------------------------------

CmpOp = Literal["==", "!=", "<", "<=", ">", ">="]


@dataclass(frozen=True)
class Imm:
    value: int


@dataclass(frozen=True)
class Var:
    name: str


Operand = Union[Imm, Var]


def operand_str(o: Operand) -> str:
    if isinstance(o, Imm):
        return str(o.value)
    return o.name


# --- Instructions ----------------------------------------------------------


@dataclass
class IConst:
    """dst assume valore imm (Kairos: local int dst = 0 poi += k, o già noto al emitter)."""

    dst: str
    value: int


@dataclass
class ICopy:
    """Copia semantica: dst diventa uguale a src (lowering Kairos = snap + add_eq, vedi emitter)."""

    dst: str
    src: str


@dataclass
class IAddEq:
    dst: str
    rhs: Operand


@dataclass
class ISubEq:
    dst: str
    rhs: Operand


@dataclass
class IXorEq:
    dst: str
    rhs: Operand


@dataclass
class ISwap:
    a: str
    b: str


@dataclass
class IHistPush:
    """Salva il valore corrente di var sulla stack history (push Kairos)."""

    hist: str
    var: str


@dataclass
class IStoreRev:
    """
    Assegnamento distruttivo reversibile: salva vecchio dst su hist, poi dst += (src - dst_old)
    in forma espansa dall'emitter (o chiama runtime mem_*).
    """

    dst: str
    src: str
    hist: str


@dataclass
class ICall:
    proc: str
    args: list[str] = field(default_factory=list)


@dataclass
class ILabel:
    name: str


@dataclass
class IBranch:
    lhs: str
    op: CmpOp
    rhs: Operand
    then_label: str
    else_label: str


@dataclass
class IJump:
    label: str


@dataclass
class IReturn:
    pass


@dataclass
class IShow:
    """Kairos `show(var)` — stampa `var: <int>` (usato per exit code da mnemo run)."""

    var: str


@dataclass
class IComment:
    text: str


@dataclass
class IIfKairos:
    """if lhs op rhs then / else? / fi lhs op rhs — condizione come in Kairos (atomi ID o numero)."""

    lhs: str
    op: CmpOp
    rhs: str
    then_instrs: list[Any]
    else_instrs: list[Any] | None = None


@dataclass
class IFromUntilKairos:
    """from entry op loop body until until_op — stessa semantica bytecode Kairos."""

    entry_lhs: str
    entry_op: CmpOp
    entry_rhs: str
    body_instrs: list[Any]
    until_lhs: str
    until_op: CmpOp
    until_rhs: str


@dataclass
class ILocalBlock:
    """local int var = 0 … delocal int var = 0 (Kairos) per scope nel corpo di un loop."""

    var: str
    body_instrs: list[Any]


Instr = Union[
    IConst,
    ICopy,
    IAddEq,
    ISubEq,
    IXorEq,
    ISwap,
    IHistPush,
    IStoreRev,
    ICall,
    ILabel,
    IBranch,
    IJump,
    IReturn,
    IShow,
    IComment,
    IIfKairos,
    IFromUntilKairos,
    ILocalBlock,
]


# --- Blocks & functions ----------------------------------------------------


@dataclass
class Block:
    bid: str
    instrs: list[Instr] = field(default_factory=list)


@dataclass
class Function:
    name: str
    params: list[tuple[str, str]]  # (tipo_ir, nome) es. ("int", "x")
    locals: list[tuple[str, str]] = field(default_factory=list)  # variabili locali dichiarate
    blocks: list[Block] = field(default_factory=list)


@dataclass
class Program:
    functions: list[Function] = field(default_factory=list)
