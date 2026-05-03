"""
Quando il layout memoria supera il numero di argomenti ammessi in una `call` Kairos,
espande le funzioni C definite nello stesso file dentro `main` (stesso spazio __mn_mem*).

Non applicabile se il sorgente usa ABI pthread (procedure worker devono restare distinte).
"""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence

import pycparser.c_ast as c

from mnemo.errors import MnemoCompileError
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
    Imm,
    Instr,
    Operand,
    Program,
    Var,
)
from mnemo.kairos_limits import MONOLITHIC_POOL_MEM_MAX

_MNEMO_PTHREAD_NAMES = frozenset(
    {
        "mnemo_pthread_parallel2",
        "mnemo_pthread_start",
        "mnemo_pthread_start1",
        "mnemo_pthread_parallel_with",
        "mnemo_pthread_parallel_with1",
    }
)


def ast_uses_mnemo_pthread(ast: c.FileAST) -> bool:
    for n in _iter_ast_nodes(ast):
        if isinstance(n, c.FuncCall) and isinstance(n.name, c.ID):
            if n.name.name in _MNEMO_PTHREAD_NAMES:
                return True
    return False


def _iter_ast_nodes(node: c.Node | None) -> Sequence[c.Node]:
    if node is None:
        return []
    out: list[c.Node] = [node]
    for _name, child in node.children():
        if isinstance(child, list):
            for ch in child:
                out.extend(_iter_ast_nodes(ch))
        else:
            out.extend(_iter_ast_nodes(child))
    return out


def _keep_name_atom(n: str) -> bool:
    if re.fullmatch(r"__mn_mem\d+", n):
        return True
    if n in ("__mn_hist", "__mn_exit"):
        return True
    if n.startswith("__mn_mtx_"):
        return True
    return False


def _should_rename_atom(n: str) -> bool:
    if _keep_name_atom(n):
        return False
    if n.startswith("__mn_il"):
        return False
    if n.startswith("__mn_e") or n.startswith("__mn_lc") or n.startswith("__mn_v_"):
        return True
    if n == "__mn_scratch":
        return True
    return False


def _rename_atom(n: str, site_id: int) -> str:
    if not _should_rename_atom(n):
        return n
    return f"__mn_il{site_id}_{n}"


def _map_operand(op: Operand, ren: Callable[[str], str]) -> Operand:
    if isinstance(op, Imm):
        return op
    return Var(ren(op.name))


def _rename_instrs(instrs: list[Instr], ren: Callable[[str], str]) -> list[Instr]:
    out: list[Instr] = []
    for ins in instrs:
        out.append(_rename_one_instr(ins, ren))
    return out


def _rename_one_instr(ins: Instr, ren: Callable[[str], str]) -> Instr:
    if isinstance(ins, IConst):
        return IConst(ren(ins.dst), ins.value)
    if isinstance(ins, ICopy):
        return ICopy(ren(ins.dst), ren(ins.src))
    if isinstance(ins, IAddEq):
        return IAddEq(ren(ins.dst), _map_operand(ins.rhs, ren))
    if isinstance(ins, ISubEq):
        return ISubEq(ren(ins.dst), _map_operand(ins.rhs, ren))
    if isinstance(ins, IXorEq):
        return IXorEq(ren(ins.dst), _map_operand(ins.rhs, ren))
    if isinstance(ins, ISwap):
        return ISwap(ren(ins.a), ren(ins.b))
    if isinstance(ins, IHistPush):
        return IHistPush(ren(ins.hist), ren(ins.var))
    if isinstance(ins, IStoreRev):
        return IStoreRev(ren(ins.dst), ren(ins.src), ren(ins.hist))
    if isinstance(ins, ICall):
        return ICall(
            ins.proc,
            [ren(a) if _should_rename_atom(a) else a for a in ins.args],
        )
    if isinstance(ins, ILabel):
        return ILabel(ins.name)
    if isinstance(ins, IBranch):
        return IBranch(
            ren(ins.lhs),
            ins.op,
            _map_operand(ins.rhs, ren),
            ins.then_label,
            ins.else_label,
        )
    if isinstance(ins, IJump):
        return IJump(ins.label)
    if isinstance(ins, IReturn):
        return IReturn()
    if isinstance(ins, IShow):
        return IShow(ren(ins.var))
    if isinstance(ins, IComment):
        return IComment(ins.text)
    if isinstance(ins, IIfKairos):
        rhs = ren(ins.rhs) if _should_rename_atom(ins.rhs) else ins.rhs
        return IIfKairos(
            ren(ins.lhs),
            ins.op,
            rhs,
            _rename_instrs(ins.then_instrs, ren),
            _rename_instrs(ins.else_instrs, ren) if ins.else_instrs else None,
        )
    if isinstance(ins, IFromUntilKairos):
        return IFromUntilKairos(
            ren(ins.entry_lhs),
            ins.entry_op,
            ren(ins.entry_rhs),
            _rename_instrs(ins.body_instrs, ren),
            ren(ins.until_lhs),
            ins.until_op,
            ren(ins.until_rhs),
        )
    if isinstance(ins, ILocalBlock):
        return ILocalBlock(
            ren(ins.var),
            _rename_instrs(ins.body_instrs, ren),
        )
    if isinstance(ins, ISsend):
        return ISsend(
            ren(ins.channel),
            [ren(x) if _should_rename_atom(x) else x for x in ins.payload_atoms],
        )
    if isinstance(ins, ISrecv):
        return ISrecv(
            [ren(x) for x in ins.dests],
            ren(ins.channel),
        )
    if isinstance(ins, IPar):
        return IPar([_rename_instrs(br, ren) for br in ins.branches])
    raise TypeError(f"inline: istruzione IR non gestita: {type(ins).__name__}")


def _is_top_decl_name(n: str) -> bool:
    """Temp creato da inline: `__mn_il{sid}__{originale}` con originale = __mn_e* / scratch / __mn_v_*."""
    m = re.match(r"^__mn_il\d+_(.+)$", n)
    if not m:
        return False
    rest = m.group(1)
    return (
        rest.startswith("__mn_e")
        or rest == "__mn_scratch"
        or rest.startswith("__mn_v_")
    )


def _collect_decl_names(instrs: list[Instr]) -> set[str]:
    """Nomi `local int` da dichiarare in testa a main (temps da funzioni inlined)."""

    found: set[str] = set()

    def maybe_add(s: str) -> None:
        if _is_top_decl_name(s):
            found.add(s)

    def scan_ins(ins: Instr) -> None:
        if isinstance(ins, IConst):
            maybe_add(ins.dst)
        elif isinstance(ins, ICopy):
            maybe_add(ins.dst)
            maybe_add(ins.src)
        elif isinstance(ins, (IAddEq, ISubEq, IXorEq)):
            maybe_add(ins.dst)
            if isinstance(ins.rhs, Var):
                maybe_add(ins.rhs.name)
        elif isinstance(ins, ISwap):
            maybe_add(ins.a)
            maybe_add(ins.b)
        elif isinstance(ins, IHistPush):
            maybe_add(ins.var)
            maybe_add(ins.hist)
        elif isinstance(ins, IStoreRev):
            maybe_add(ins.dst)
            maybe_add(ins.src)
            maybe_add(ins.hist)
        elif isinstance(ins, ICall):
            for a in ins.args:
                maybe_add(a)
        elif isinstance(ins, IBranch):
            maybe_add(ins.lhs)
            if isinstance(ins.rhs, Var):
                maybe_add(ins.rhs.name)
        elif isinstance(ins, IShow):
            maybe_add(ins.var)
        elif isinstance(ins, IIfKairos):
            maybe_add(ins.lhs)
            maybe_add(ins.rhs)
            walk(ins.then_instrs)
            if ins.else_instrs:
                walk(ins.else_instrs)
            return
        elif isinstance(ins, IFromUntilKairos):
            maybe_add(ins.entry_lhs)
            maybe_add(ins.entry_rhs)
            maybe_add(ins.until_lhs)
            maybe_add(ins.until_rhs)
            walk(ins.body_instrs)
            return
        elif isinstance(ins, ILocalBlock):
            walk(ins.body_instrs)
            return
        elif isinstance(ins, ISsend):
            maybe_add(ins.channel)
            for p in ins.payload_atoms:
                maybe_add(p)
        elif isinstance(ins, ISrecv):
            maybe_add(ins.channel)
            for d in ins.dests:
                maybe_add(d)
        elif isinstance(ins, IPar):
            for br in ins.branches:
                walk(br)
            return

    def walk(lst: list[Instr]) -> None:
        for ins in lst:
            scan_ins(ins)

    walk(instrs)
    return found


def _expand_user_calls(
    instrs: list[Instr],
    *,
    fn_by_name: dict[str, Function],
    defined: frozenset[str],
    counter: list[int],
) -> list[Instr]:
    def expand_one(lst: list[Instr]) -> list[Instr]:
        res: list[Instr] = []
        for ins in lst:
            if isinstance(ins, ICall) and ins.proc in defined:
                callee = fn_by_name.get(ins.proc)
                if callee is None:
                    raise MnemoCompileError(
                        f"inline: funzione {ins.proc!r} non trovata nell'IR"
                    )
                sid = counter[0]
                counter[0] += 1
                ren = lambda n, s=sid: _rename_atom(n, s)  # noqa: E731
                body = callee.blocks[0].instrs
                cloned = _rename_instrs(body, ren)
                res.extend(expand_one(cloned))
            elif isinstance(ins, IIfKairos):
                res.append(
                    IIfKairos(
                        ins.lhs,
                        ins.op,
                        ins.rhs,
                        expand_one(ins.then_instrs),
                        expand_one(ins.else_instrs) if ins.else_instrs else None,
                    )
                )
            elif isinstance(ins, IFromUntilKairos):
                res.append(
                    IFromUntilKairos(
                        ins.entry_lhs,
                        ins.entry_op,
                        ins.entry_rhs,
                        expand_one(ins.body_instrs),
                        ins.until_lhs,
                        ins.until_op,
                        ins.until_rhs,
                    )
                )
            elif isinstance(ins, ILocalBlock):
                res.append(
                    ILocalBlock(ins.var, expand_one(ins.body_instrs))
                )
            elif isinstance(ins, IPar):
                res.append(IPar([expand_one(br) for br in ins.branches]))
            else:
                res.append(ins)
        return res

    return expand_one(instrs)


def _inline_scratch_stack_name(n: str) -> bool:
    """`push`/`pop` Kairos accettano solo stack/channel, non int."""
    return bool(re.fullmatch(r"__mn_il\d+___mn_scratch", n))


def _merge_main_locals(
    orig: Function, main_instrs: list[Instr]
) -> list[tuple[str, str]]:
    decl_extra = sorted(_collect_decl_names(main_instrs))
    base_ints = [(t, n) for t, n in orig.locals if t == "int"]
    stacks = [(t, n) for t, n in orig.locals if t == "stack"]
    channels = [(t, n) for t, n in orig.locals if t == "channel"]
    seen = {n for _t, n in base_ints} | {n for _t, n in stacks} | {n for _t, n in channels}
    added: list[tuple[str, str]] = []
    for n in decl_extra:
        if n in seen:
            continue
        if _inline_scratch_stack_name(n):
            added.append(("stack", n))
        else:
            added.append(("int", n))
    return base_ints + added + stacks + channels


def maybe_inline_user_functions(
    ast: c.FileAST,
    prog: Program,
    *,
    total_mem_cells: int,
) -> Program:
    if total_mem_cells <= MONOLITHIC_POOL_MEM_MAX:
        return prog
    if ast_uses_mnemo_pthread(ast):
        raise MnemoCompileError(
            "layout memoria troppo grande per le `call` Kairos con ABI pthread: "
            "riduci celle / ptr pool oppure evita mnemo_pthread_* in questo file."
        )

    defined = frozenset(
        ext.decl.name
        for ext in ast.ext
        if isinstance(ext, c.FuncDef)
        and ext.decl.name
        and ext.decl.name != "main"
    )
    if not defined:
        return prog

    fn_by_name = {f.name: f for f in prog.functions}
    main = fn_by_name.get("main")
    if main is None:
        return prog

    counter = [0]
    new_instrs = _expand_user_calls(
        main.blocks[0].instrs,
        fn_by_name=fn_by_name,
        defined=defined,
        counter=counter,
    )
    new_locals = _merge_main_locals(main, new_instrs)
    new_main = Function(
        name="main",
        params=[],
        locals=new_locals,
        blocks=[Block(main.blocks[0].bid, new_instrs)],
    )
    return Program(functions=[new_main])
