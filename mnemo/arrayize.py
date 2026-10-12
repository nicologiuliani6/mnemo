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
- Il lowering indicizza a runtime con catene `if ix==0 … else if ix==k …` il cui
  ramo k è lo stesso schema sulla cella base+k: qui la catena diventa un solo
  accesso `__mn_mem[(base + ix)]` (O(1) invece di O(N)).
"""

from __future__ import annotations

import re

from dataclasses import fields, replace

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
# cella a indice calcolato (catene affini): __mn_mem<base>+<ix>[+<iy>…]
_ANY_CELL = re.compile(r"__mn_mem(\d+)((?:\+\w+)*)\b")


def _cell_idx(name: str) -> int | None:
    m = _CELL.fullmatch(name)
    return int(m.group(1)) if m else None


def _map_names(x, fn):
    """Applica `fn` a ogni stringa di un'istruzione IR (nomi, guardie, Var),
    ricorsivamente nei corpi annidati."""
    if isinstance(x, str):
        return fn(x)
    if isinstance(x, Var):
        return Var(fn(x.name))
    if isinstance(x, list):
        return [_map_names(e, fn) for e in x]
    if hasattr(x, "__dataclass_fields__") and not isinstance(x, Imm):
        return replace(x, **{fl.name: _map_names(getattr(x, fl.name), fn) for fl in fields(x)})
    return x


_CELL_CALL = re.compile(r"I(?:Un)?[Cc]all\(proc='[^']*', args=\[[^\]]*__mn_mem\d")


def _has_cell_call(instrs: list) -> bool:
    """Corpo con call che ricevono celle, par o try: non lo si riscrive."""
    r = repr(instrs)
    return bool(_CELL_CALL.search(r)) or "IPar(" in r or "ITry(" in r


def _affine_chain(ins) -> list | None:
    """Se `ins` è una catena `if ix==0 then B0 else if ix==1 then B1 … fi` in cui
    B_k è B_0 con ogni cella spostata di k, ritorna B_0 con le celle riscritte
    `__mn_mem<base>+<ix>`; altrimenti None."""
    ix = ins.lhs
    bodies = []
    node = ins
    while True:
        if not (isinstance(node, IIfKairos) and node.lhs == ix and node.op == "=="
                and node.rhs == str(len(bodies))):
            return None
        bodies.append(node.then_instrs)
        if node.else_instrs is None:
            break
        if len(node.else_instrs) != 1:
            return None
        node = node.else_instrs[0]
    if len(bodies) < 2 or not _CELL.search(repr(bodies[0])) or _has_cell_call(bodies[0]):
        return None

    def shift(k):
        return lambda s: _CELL.sub(lambda m: f"__mn_mem{int(m.group(1)) - k}", s)

    norm0 = repr(bodies[0])
    for k in range(1, len(bodies)):
        if repr(_map_names(bodies[k], shift(k))) != norm0:
            return None
    return _map_names(bodies[0], lambda s: _CELL.sub(lambda m: f"{m.group(0)}+{ix}", s))


class _Fn:
    """Stato per procedura: come si scrive la cella K e i temporanei freschi."""

    def __init__(self, window: int, owns_right: bool) -> None:
        self.window = window
        self.owns_right = owns_right
        self.right = False  # dentro un ramo destro di `par`
        self.par_pre: list = []   # copie celle condivise, prima del par
        self.par_post: list = []  # e il loro annullamento, dopo
        self.n_tmp = 0

    def ref(self, k: int, off: str = "") -> str:
        """Cella k (più gli indici runtime `off` = "+ix+iy…")."""
        arr, base = MEM, k
        if k >= self.window:
            if not self.owns_right:
                raise MnemoCompileError(
                    f"arrayize: cell {k} outside the window ({self.window}) outside main"
                )
            arr, base = MEM_R, k - self.window
        if not off:
            return f"{arr}[{base}]"
        terms = " + ".join([str(base)] + [self.sub(v) for v in off[1:].split("+")])
        return f"{arr}[({terms})]"

    def cell(self, name: str) -> str | None:
        """Riferimento Kairos se `name` è una cella (statica o calcolata)."""
        m = _ANY_CELL.fullmatch(name)
        return self.ref(int(m.group(1)), m.group(2)) if m else None

    def tmp(self) -> str:
        self.n_tmp += 1
        return f"__mn_ax{self.n_tmp}"

    def sub(self, s: str) -> str:
        """Riscrive ogni `__mn_memK` in una stringa (nome o espressione)."""
        return _ANY_CELL.sub(lambda m: self.ref(int(m.group(1)), m.group(2)), s)

    def op(self, o):
        if isinstance(o, Var):
            return Var(self.sub(o.name))
        return o


def _array_of(cell_ref: str) -> str | None:
    i = cell_ref.find("[")
    return cell_ref[:i] if i > 0 else None


def _assign(f: _Fn, cls, dst: str, rhs) -> list:
    d = f.sub(dst)
    r = f.op(rhs)
    arr = _array_of(d)
    if arr is not None and isinstance(r, Var) and re.search(rf"\b{arr}\[", r.name):
        # `a[i] += a[j]`: Kairos vieta il nome dell'array a destra.
        t = f.tmp()
        return [ILocalBlock(t, [IAddEq(t, r), cls(d, Var(t)), ISubEq(t, r)])]
    return [cls(d, r)]


def _call_args(f: _Fn, args: list[str], callee: Function | None) -> tuple[list[str], list[tuple]]:
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
        # Gli argomenti di una call Kairos devono essere distinti: una cella
        # ripetuta (x & x) arriva alla seconda posizione come copia della prima
        # (sola lettura), segnata con c = None.
        moved: list[tuple[str | None, str]] = []
        seen: dict[str, str] = {}
        out = []
        for a in args:
            c = f.cell(a)
            if c is None:
                out.append(a)
                continue
            if a in seen:
                t = f.tmp()
                moved.append((None, t, seen[a]))
                out.append(t)
                continue
            seen[a] = f.tmp()
            moved.append((c, seen[a], None))
            out.append(seen[a])
        if len(moved) > 8:
            # guardia: decine di celle passate una a una a una procedura di
            # libreria = memoria non collassata nell'array (bug a monte), e
            # produrrebbe un annidamento enorme di temporanei.
            raise MnemoCompileError(
                f"arrayize: {len(moved)} cells passed one by one to a library call"
            )
        return out, moved
    if len(mem_pos) != len(formal_mem):
        raise MnemoCompileError(
            f"arrayize: call {callee.name}: {len(mem_pos)} cells for {len(formal_mem)} formals"
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
        raise MnemoCompileError(f"arrayize: call {callee.name}: misaligned cells {sorted(shifts)}")
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
    return _fix_indices(f, out)


_ARR_REF = re.compile(rf"(?:{MEM_R}|{MEM})\[")


def _split_ref(ref: str) -> tuple[str, str] | None:
    """`arr[idx]` -> (arr, idx), con idx fra le parentesi quadre esterne."""
    m = _ARR_REF.match(ref)
    if not m or not ref.endswith("]"):
        return None
    return ref[: m.end() - 1], ref[m.end():-1]


def _inner_refs(idx: str) -> list[str]:
    """Riferimenti a cella (anche annidati) che compaiono nell'indice."""
    out, i = [], 0
    while True:
        m = _ARR_REF.search(idx, i)
        if not m:
            return out
        depth, j = 0, m.end() - 1
        while j < len(idx):
            depth += idx[j] == "["
            depth -= idx[j] == "]"
            if depth == 0:
                break
            j += 1
        out.append(idx[m.start(): j + 1])
        i = j + 1


def _hoist_dst(f: _Fn, dst: str, make) -> list:
    """Kairos vieta che l'indice della cella scritta legga lo stesso array
    (`m[(4 + m[407])] -= t`): le celle dell'indice passano per temporanei,
    letti prima e azzerati dopo. Se l'indice nomina la cella scritta stessa
    l'azzeramento fallisce: e' davvero un'operazione non reversibile."""
    sp = _split_ref(dst)
    if sp is None:
        return [make(dst)]
    arr, idx = sp
    inner = [r for r in _inner_refs(idx)]
    if not inner:
        return [make(dst)]
    temps = []
    for r in inner:
        t = f.tmp()
        idx = idx.replace(r, t)
        temps.append((t, r))
    body = [make(f"{arr}[{idx}]")]
    for t, r in reversed(temps):
        body = [ILocalBlock(t, [IAddEq(t, Var(r))] + body + [ISubEq(t, Var(r))])]
    return body


def _fix_indices(f: _Fn, instrs: list) -> list:
    out: list = []
    for ins in instrs:
        if isinstance(ins, ILocalBlock):
            out.append(ILocalBlock(ins.var, _fix_indices(f, ins.body_instrs)))
        elif isinstance(ins, (IAddEq, ISubEq, IXorEq)):
            cls = type(ins)
            out.extend(_hoist_dst(f, ins.dst, lambda d, c=cls, r=ins.rhs: c(d, r)))
        elif isinstance(ins, IConst):
            out.extend(_hoist_dst(f, ins.dst, lambda d, v=ins.value: IConst(d, v)))
        elif isinstance(ins, ISwap):
            a = _hoist_dst(f, ins.a, lambda d: d)
            if len(a) == 1 and isinstance(a[0], str):
                out.extend(_hoist_dst(f, ins.b, lambda d, x=ins.a: ISwap(x, d)))
            else:
                t = f.tmp()  # scambio con indici calcolati: passa per un temporaneo
                out.extend(_fix_indices(f, [ILocalBlock(t, [
                    IAddEq(t, Var(ins.a)), ISubEq(ins.a, Var(t)),
                    IAddEq(ins.a, Var(ins.b)), ISubEq(ins.b, Var(ins.a)),
                    IAddEq(ins.b, Var(t)), ISubEq(t, Var(ins.b))])]))
        else:
            out.append(ins)
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
        c = f.cell(ins.var)
        if c is None:
            return [ins]
        t = f.tmp()
        return [ILocalBlock(t, [IAddEq(t, Var(c)), ISubEq(c, Var(t)), IHistPush(ins.hist, t)])]
    if isinstance(ins, IShow):
        c = f.cell(ins.var)
        if c is None:
            return [ins]
        t = f.tmp()
        return [ILocalBlock(t, [IAddEq(t, Var(c)), IShow(t, ins.as_char), ISubEq(t, Var(c))])]
    if isinstance(ins, ISsend):
        pre, atoms = [], []
        for a in ins.payload_atoms:
            c = f.cell(a)
            if c is None:
                atoms.append(a)
                continue
            t = f.tmp()
            pre.append((t, [IAddEq(t, Var(c)), ISubEq(c, Var(t))]))
            atoms.append(t)
        body: list = [ISsend(ins.channel, atoms)]
        for t, mv in reversed(pre):
            body = [ILocalBlock(t, mv + body)]
        return body
    if isinstance(ins, ISrecv):
        post, dests = [], []
        for d in ins.dests:
            c = f.cell(d)
            if c is None:
                dests.append(d)
                continue
            t = f.tmp()
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
        for c, t, first in reversed(moved):
            if c is None:
                body = [ILocalBlock(t, [IAddEq(t, Var(first))] + body + [ISubEq(t, Var(first))])]
                continue
            body = [ILocalBlock(t, [IAddEq(t, Var(c)), ISubEq(c, Var(t))] + body
                                + [IAddEq(c, Var(t)), ISubEq(t, Var(c))])]
        return body
    if isinstance(ins, IIfKairos):
        body = _affine_chain(ins)
        if body is not None:
            return _seq(f, body, fns)
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
                     _seq(f, ins.rollback_instrs, fns) if ins.rollback_instrs is not None else None,
                     (f.sub(ins.yrt[0]), ins.yrt[1], f.sub(ins.yrt[2])) if ins.yrt else None)]
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
                raise MnemoCompileError(f"arrayize: {fn.name} has cells both as parameters and as locals")
            params = [p for i, p in enumerate(fn.params) if i not in set(pos)]
            params.insert(pos[0], ("int[]", MEM))
            fn.params = params
        if owns:
            locals_ = [lv for lv in fn.locals if not (lv[0] == "int" and _cell_idx(lv[1]) is not None)]
            arrays = [(f"int[{window}]", MEM)]
            if physical > window:
                arrays.append((f"int[{window}]", MEM_R))
            fn.locals = arrays + locals_
