"""
IR → IR: le celle di memoria `__mn_mem{K}` diventano celle di un array Kairos.

Il lowering ragiona su celle con nome (`__mn_mem0 … __mn_mem{N-1}`); qui, prima
dell'emissione, la memoria diventa un unico `int __mn_mem[S]` (la finestra) e,
quando un `par` usa due finestre disgiunte, un secondo `int __mn_memR[S]` per il
ramo destro (rami diversi di un `par` non possono usare lo stesso array).

- Procedure: i parametri cella spariscono, al loro posto `int __mn_mem[]`
  (per riferimento); le call passano l'array del chiamante, o `__mn_memR` se le
  celle passate sono quelle della finestra destra.
- Kairos accetta una cella `a[i]` come luogo di `+= -= ^=` e nelle espressioni,
  ma non dove serve un identificatore (push, show, ssend/srecv, argomenti di
  call): lì la cella passa per un temporaneo `local … delocal`.
- `a[i] += e` non può citare `a` in `e`: anche lì un temporaneo.
"""

from __future__ import annotations

import re

from mnemo.errors import MnemoCompileError
from mnemo.ir import (
    Function,
    IAddEq,
    ICall,
    IConst,
    IFromUntilKairos,
    IHistPush,
    IIfKairos,
    ILocalBlock,
    IPar,
    IShow,
    ISrecv,
    ISsend,
    ISubEq,
    ISwap,
    ITry,
    IUncall,
    IXorEq,
    Imm,
    Program,
    Var,
)

MEM = "__mn_mem"
MEM_R = "__mn_memR"
_CELL = re.compile(r"__mn_mem(\d+)\b")


def _cell_idx(name: str) -> int | None:
    m = _CELL.fullmatch(name)
    return int(m.group(1)) if m else None


class _Fn:
    """Stato per procedura: come si scrive la cella K e i temporanei freschi."""

    def __init__(self, window: int, owns_right: bool) -> None:
        self.window = window
        self.owns_right = owns_right
        self.right = False  # dentro un ramo destro di `par`
        self.par_pre: list = []   # copie celle condivise, prima del par
        self.par_post: list = []  # e il loro annullamento, dopo
        self.n_tmp = 0

    def ref(self, k: int) -> str:
        if k < self.window:
            return f"{MEM}[{k}]"
        if not self.owns_right:
            raise MnemoCompileError(
                f"arrayize: cella {k} fuori dalla finestra ({self.window}) fuori da main"
            )
        return f"{MEM_R}[{k - self.window}]"

    def tmp(self) -> str:
        self.n_tmp += 1
        return f"__mn_ax{self.n_tmp}"

    def sub(self, s: str) -> str:
        """Riscrive ogni `__mn_memK` in una stringa (nome o espressione)."""
        return _CELL.sub(lambda m: self.ref(int(m.group(1))), s)

    def op(self, o):
        if isinstance(o, Var):
            return Var(self.sub(o.name))
        return o


def _array_of(cell_ref: str) -> str | None:
    i = cell_ref.find("[")
    return cell_ref[:i] if i > 0 else None


def _wrap_id(f: _Fn, name: str, use) -> list:
    """`use(t)` dove serviva un identificatore e c'era la cella `name`:
    t riceve il valore (spostato: la cella va a 0), poi torna nella cella."""
    k = _cell_idx(name)
    if k is None:
        return use(name)
    c = f.ref(k)
    t = f.tmp()
    return [
        ILocalBlock(
            t,
            [IAddEq(t, Var(c)), ISubEq(c, Var(t))]
            + use(t)
            + [IAddEq(c, Var(t)), ISubEq(t, Var(c))],
        )
    ]


def _assign(f: _Fn, cls, dst: str, rhs) -> list:
    d = f.sub(dst)
    r = f.op(rhs)
    arr = _array_of(d)
    if arr is not None and isinstance(r, Var) and re.search(rf"\b{arr}\[", r.name):
        # `a[i] += a[j]`: Kairos vieta il nome dell'array a destra.
        t = f.tmp()
        return [ILocalBlock(t, [IAddEq(t, r), cls(d, Var(t)), ISubEq(t, r)])]
    return [cls(d, r)]


def _call_args(f: _Fn, args: list[str], callee: Function | None) -> tuple[list[str], list[tuple[str, str]]]:
    """Collassa gli argomenti cella nel nome dell'array; ritorna anche le celle
    passate per valore a formali int (da spostare in temporanei)."""
    if callee is None and f"{MEM}0" in args:
        # procedure pool del preludio: la memoria arriva come sequenza contigua
        # __mn_mem0 … __mn_mem{N-1} → l'array; le altre celle (slot/out che
        # sono a loro volta celle) restano int per riferimento.
        s = args.index(f"{MEM}0")
        e = s
        while e < len(args) and _cell_idx(args[e]) == e - s:
            e += 1
        if e - s > 1:
            args = args[:s] + [MEM] + args[e:]
    mem_pos = [i for i, a in enumerate(args) if _cell_idx(a) is not None]
    formal_mem = (
        [i for i, (_t, n) in enumerate(callee.params) if _cell_idx(n) is not None]
        if callee is not None
        else []
    )
    if not formal_mem:
        # callee senza parametri cella (libreria): ogni cella è un int per riferimento
        moved: list[tuple[str, str]] = []
        seen: dict[str, str] = {}
        out = []
        for a in args:
            if _cell_idx(a) is None:
                out.append(a)
                continue
            if a not in seen:
                seen[a] = f.tmp()
                moved.append((f.ref(_cell_idx(a)), seen[a]))
            out.append(seen[a])
        if len(moved) > 8:
            # guardia: decine di celle passate una a una a una procedura di
            # libreria = memoria non collassata nell'array (bug a monte), e
            # produrrebbe un annidamento enorme di temporanei.
            raise MnemoCompileError(
                f"arrayize: {len(moved)} celle passate singolarmente a una call di libreria"
            )
        return out, moved
    if len(mem_pos) != len(formal_mem):
        raise MnemoCompileError(
            f"arrayize: call {callee.name}: {len(mem_pos)} celle per {len(formal_mem)} formali"
        )
    shifts = {
        _cell_idx(args[a]) - _cell_idx(callee.params[p][1])
        for a, p in zip(mem_pos, formal_mem)
    }
    if f.right and shifts <= {0, f.window}:
        # ramo destro di un par: mai lo stesso array del sinistro (race su
        # __mn_mem); le celle condivise (shift 0) sono copiate prima del par
        arr = MEM_R
    elif shifts == {0}:
        arr = MEM
    elif shifts <= {0, f.window} and f.owns_right:
        arr = MEM_R  # finestra destra; le celle condivise sono copiate prima del par
    else:
        raise MnemoCompileError(f"arrayize: call {callee.name}: celle non allineate {sorted(shifts)}")
    out = [a for i, a in enumerate(args) if i not in set(mem_pos)]
    out.insert(mem_pos[0], arr)
    return out, []


def _shared_into_right(f: _Fn, args: list[str], callee: Function) -> list[tuple[int, int]]:
    """Celle condivise (stesso indice a sinistra) passate al ramo destro: (k_left, k_right)."""
    formal = [n for _t, n in callee.params if _cell_idx(n) is not None]
    cells = [a for a in args if _cell_idx(a) is not None]
    out = []
    for a, p in zip(cells, formal):
        ka, kp = _cell_idx(a), _cell_idx(p)
        if ka == kp:
            out.append((ka, kp))
    return out


def _seq(f: _Fn, instrs: list, fns: dict[str, Function]) -> list:
    out: list = []
    for ins in instrs:
        out.extend(_one(f, ins, fns))
    return out


def _one(f: _Fn, ins, fns: dict[str, Function]) -> list:
    if isinstance(ins, IConst):
        return [IConst(f.sub(ins.dst), ins.value)]
    if isinstance(ins, (IAddEq, ISubEq, IXorEq)):
        return _assign(f, type(ins), ins.dst, ins.rhs)
    if isinstance(ins, ISwap):
        a, b = f.sub(ins.a), f.sub(ins.b)
        if _array_of(a) is not None and _array_of(a) == _array_of(b):
            t = f.tmp()  # a[i] <=> a[j] via temporaneo
            return [ILocalBlock(t, [IAddEq(t, Var(a)), ISubEq(a, Var(t)),
                                    IAddEq(a, Var(b)), ISubEq(b, Var(a)),
                                    IAddEq(b, Var(t)), ISubEq(t, Var(b))])]
        return [ISwap(a, b)]
    if isinstance(ins, IHistPush):
        k = _cell_idx(ins.var)
        if k is None:
            return [ins]
        c, t = f.ref(k), f.tmp()
        return [ILocalBlock(t, [IAddEq(t, Var(c)), ISubEq(c, Var(t)), IHistPush(ins.hist, t)])]
    if isinstance(ins, IShow):
        k = _cell_idx(ins.var)
        if k is None:
            return [ins]
        c, t = f.ref(k), f.tmp()
        return [ILocalBlock(t, [IAddEq(t, Var(c)), IShow(t, ins.as_char), ISubEq(t, Var(c))])]
    if isinstance(ins, ISsend):
        pre, atoms = [], []
        for a in ins.payload_atoms:
            k = _cell_idx(a)
            if k is None:
                atoms.append(a)
                continue
            c, t = f.ref(k), f.tmp()
            pre.append((t, [IAddEq(t, Var(c)), ISubEq(c, Var(t))]))
            atoms.append(t)
        body: list = [ISsend(ins.channel, atoms)]
        for t, mv in reversed(pre):
            body = [ILocalBlock(t, mv + body)]
        return body
    if isinstance(ins, ISrecv):
        post, dests = [], []
        for d in ins.dests:
            k = _cell_idx(d)
            if k is None:
                dests.append(d)
                continue
            c, t = f.ref(k), f.tmp()
            post.append((t, [IAddEq(c, Var(t)), ISubEq(t, Var(c))]))
            dests.append(t)
        body = [ISrecv(dests, ins.channel)]
        for t, mv in reversed(post):
            body = [ILocalBlock(t, body + mv)]
        return body
    if isinstance(ins, (ICall, IUncall)):
        callee = fns.get(ins.proc)
        args, moved = _call_args(f, ins.args, callee)
        pre: list = []
        post: list = []
        if callee is not None and MEM_R in args:
            for kl, kr in _shared_into_right(f, ins.args, callee):
                # copia la cella condivisa nella finestra destra (sola lettura nel ramo)
                pre.append(IAddEq(f"{MEM_R}[{kr}]", Var(f.ref(kl))))
                post.append(ISubEq(f"{MEM_R}[{kr}]", Var(f.ref(kl))))
        if f.right:
            # dentro il ramo il sinistro scrive __mn_mem: la copia va fuori dal par
            f.par_pre += pre
            f.par_post += post
            pre, post = [], []
        body = pre + [type(ins)(ins.proc, args)] + post
        for c, t in reversed(moved):
            body = [ILocalBlock(t, [IAddEq(t, Var(c)), ISubEq(c, Var(t))] + body
                                + [IAddEq(c, Var(t)), ISubEq(t, Var(c))])]
        return body
    if isinstance(ins, IIfKairos):
        return [IIfKairos(f.sub(ins.lhs), ins.op, f.sub(ins.rhs),
                          _seq(f, ins.then_instrs, fns),
                          _seq(f, ins.else_instrs, fns) if ins.else_instrs is not None else None)]
    if isinstance(ins, IFromUntilKairos):
        return [IFromUntilKairos(f.sub(ins.entry_lhs), ins.entry_op, f.sub(ins.entry_rhs),
                                 _seq(f, ins.body_instrs, fns),
                                 f.sub(ins.until_lhs), ins.until_op, f.sub(ins.until_rhs),
                                 _seq(f, ins.body2_instrs, fns))]
    if isinstance(ins, ILocalBlock):
        return [ILocalBlock(ins.var, _seq(f, ins.body_instrs, fns))]
    if isinstance(ins, ITry):
        return [ITry(f.sub(ins.lhs), ins.op, f.sub(ins.rhs),
                     _seq(f, ins.body_instrs, fns),
                     _seq(f, ins.rollback_instrs, fns) if ins.rollback_instrs is not None else None)]
    if isinstance(ins, IPar):
        branches = []
        saved = (f.right, f.par_pre, f.par_post)
        f.par_pre, f.par_post = [], []
        for i, br in enumerate(ins.branches):
            f.right = i > 0 and f.owns_right
            branches.append(_seq(f, br, fns))
        pre, post = f.par_pre, f.par_post
        f.right, f.par_pre, f.par_post = saved
        return pre + [IPar(branches)] + post
    return [ins]


def arrayize_program(prog: Program, *, window: int, physical: int) -> None:
    """Trasforma `prog` sul posto. `window` = celle di una finestra (S),
    `physical` = celle totali (S, o 2S con la partizione `par`)."""
    # le call vanno riscritte guardando i parametri originali del callee
    snapshot = {fn.name: Function(fn.name, list(fn.params)) for fn in prog.functions}
    for fn in prog.functions:
        cell_locals = [n for t, n in fn.locals if t == "int" and _cell_idx(n) is not None]
        owns = bool(cell_locals)
        f = _Fn(window, owns_right=owns and physical > window)
        for b in fn.blocks:
            b.instrs = _seq(f, b.instrs, snapshot)
        pos = [i for i, (_t, n) in enumerate(fn.params) if _cell_idx(n) is not None]
        if pos:
            if owns:
                raise MnemoCompileError(f"arrayize: {fn.name} ha celle sia param sia local")
            params = [p for i, p in enumerate(fn.params) if i not in set(pos)]
            params.insert(pos[0], ("int[]", MEM))
            fn.params = params
        if owns:
            locals_ = [lv for lv in fn.locals if not (lv[0] == "int" and _cell_idx(lv[1]) is not None)]
            arrays = [(f"int[{window}]", MEM)]
            if physical > window:
                arrays.append((f"int[{window}]", MEM_R))
            fn.locals = arrays + locals_
