"""
Lowering pycparser AST → IR Mnemo.

- `int main(void)`; altre funzioni `void|int|unsigned|bool|_Bool` con corpo C → procedure Kairos.
- Convenzione ritorno: `int f(...)` → `procedure f(..., int __mn_ret)`; `call f(a, b, t)` con `t` azzerato.
- Tipi scalari (tutti `int` in Kairos): int, unsigned int, unsigned, _Bool, bool.
- Espressioni: letterali, ID, + - * / %, unario -, cast verso scalari, chiamate `int f()` come espressione.
- Controllo: `if` (anche `&&`/`||`), `while`/`do…while`/`for`, `break`/`continue` nei cicli, `switch`/`case`.
- `int main(int argc, char **argv)`: `argc` da `// mnemo-main-argc: N` (default 0 se assente); `argv` è stub `int` = 0 (non usabile come puntatore).
- Assegnamenti `+=`, `-=`, `*=`, `/=`, `%=`.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pycparser.c_ast as c

from mnemo.errors import MnemoCompileError
from mnemo.ir import (
    Block,
    CmpOp,
    Function,
    IAddEq,
    ICall,
    IComment,
    IConst,
    IFromUntilKairos,
    IHistPush,
    IIfKairos,
    ILocalBlock,
    IReturn,
    ISubEq,
    Instr,
    Program,
    Imm,
    Var,
)

BUILTIN_KAIROS_PROCS = frozenset(
    {"__mn_mul_into", "__mn_divmod_nonneg", "__mn_mod_nonneg"}
)

MN_RET = "__mn_ret"

_CMP_OPS: frozenset[str] = frozenset({"==", "!=", "<", "<=", ">", ">="})

_NEG_CMP: dict[CmpOp, CmpOp] = {
    "==": "!=",
    "!=": "==",
    "<": ">=",
    "<=": ">",
    ">": "<=",
    ">=": "<",
}

_SCALAR_NAMES = frozenset(
    {
        ("int",),
        ("unsigned", "int"),
        ("unsigned",),
        ("_Bool",),
        ("bool",),
    }
)


def _is_scalar_type_names(names: list[str]) -> bool:
    return tuple(names) in _SCALAR_NAMES


@dataclass
class _LoopFrame:
    br_var: str | None
    ct_var: str | None


@dataclass
class _Ctx:
    hist: str = "__mn_hist"
    scratch: str = "__mn_scratch"
    temp_i: int = 0
    int_locals: set[str] = field(default_factory=set)
    decl_order: list[str] = field(default_factory=list)
    extern_procs: frozenset[str] = field(default_factory=frozenset)
    proc_returns_int: dict[str, bool] = field(default_factory=dict)
    param_names: frozenset[str] = field(default_factory=frozenset)
    is_main: bool = True
    returns_int: bool = False
    ret_var: str | None = None
    use_hist: bool = False
    use_scratch: bool = False
    loop_stack: list[_LoopFrame] = field(default_factory=list)

    def fresh_temp(self) -> str:
        name = f"__mn_e{self.temp_i}"
        self.temp_i += 1
        self.int_locals.add(name)
        return name


def _scalar_decl_name(node: c.Decl) -> str | None:
    t = node.type
    if not isinstance(t, c.TypeDecl):
        return None
    inner = t.type
    if not isinstance(inner, c.IdentifierType):
        return None
    if not _is_scalar_type_names(inner.names):
        return None
    if t.declname is None:
        return None
    return str(t.declname)


def _func_return_is_void(fd: c.FuncDecl) -> bool:
    rt = fd.type
    if not isinstance(rt, c.TypeDecl) or not isinstance(rt.type, c.IdentifierType):
        raise MnemoCompileError("tipo di ritorno non supportato")
    return rt.type.names == ["void"]


def _callable_returns_int(fd: c.FuncDecl) -> bool:
    if _func_return_is_void(fd):
        return False
    rt = fd.type
    assert isinstance(rt, c.TypeDecl) and isinstance(rt.type, c.IdentifierType)
    if not _is_scalar_type_names(rt.type.names):
        raise MnemoCompileError(f"tipo di ritorno non scalar: {list(rt.type.names)!r}")
    return True


def _pointer_level(decl_type: c.Node) -> int:
    n = 0
    cur: c.Node = decl_type
    while isinstance(cur, c.PtrDecl):
        n += 1
        cur = cur.type
    while isinstance(cur, c.ArrayDecl):
        n += 1
        cur = cur.type
    return n


def _type_leaf(decl_type: c.Node) -> tuple[list[str], str | None]:
    cur: c.Node = decl_type
    while isinstance(cur, c.PtrDecl):
        cur = cur.type
    while isinstance(cur, c.ArrayDecl):
        cur = cur.type
    if isinstance(cur, c.TypeDecl) and isinstance(cur.type, c.IdentifierType):
        return list(cur.type.names), cur.declname
    raise MnemoCompileError("tipo parametro malformato")


def _parse_main_param(decl: c.Decl) -> tuple[str, str]:
    names, declname = _type_leaf(decl.type)
    if declname is None:
        raise MnemoCompileError("parametro main senza nome")
    name = str(declname)
    pl = _pointer_level(decl.type)
    if names == ["int"] and pl == 0:
        return name, "argc"
    if names == ["char"] and pl >= 2:
        return name, "argv"
    raise MnemoCompileError(
        f"firma main: parametro {name!r} non supportato (int argc, char **argv)"
    )


def _main_locals_from_fd(fd: c.FuncDecl) -> list[tuple[str, str]]:
    if fd.args is None:
        return []
    plist = fd.args.params
    if len(plist) == 1 and isinstance(plist[0], c.Typename):
        ty = plist[0].type
        if isinstance(ty, c.TypeDecl) and isinstance(ty.type, c.IdentifierType):
            if ty.type.names == ["void"]:
                return []
        raise MnemoCompileError("main: lista parametri non supportata")
    out: list[tuple[str, str]] = []
    for p in plist:
        if isinstance(p, c.Decl):
            out.append(_parse_main_param(p))
        else:
            raise MnemoCompileError("parametro main non supportato")
    if len(out) >= 2:
        if out[0][1] != "argc" or out[1][1] != "argv":
            raise MnemoCompileError("main: usare int argc poi char **argv")
    if len(out) == 1 and out[0][1] != "argc":
        raise MnemoCompileError("main: con un parametro solo, deve essere int argc")
    return out


def _func_param_names(fd: c.FuncDecl) -> list[str]:
    if fd.args is None:
        return []
    names: list[str] = []
    for p in fd.args.params:
        if isinstance(p, c.Typename):
            ty = p.type
            if isinstance(ty, c.TypeDecl) and isinstance(ty.type, c.IdentifierType):
                if ty.type.names == ["void"]:
                    continue
            raise MnemoCompileError("parametro Typename non supportato")
        elif isinstance(p, c.Decl):
            n = _scalar_decl_name(p)
            if n is None:
                raise MnemoCompileError("tipo parametro non supportato")
            names.append(n)
        else:
            raise MnemoCompileError(f"parametro non supportato: {type(p).__name__}")
    return names


def _merge_proc_returns_int(ast: c.FileAST) -> dict[str, bool]:
    sig: dict[str, bool] = {n: False for n in BUILTIN_KAIROS_PROCS}
    for ext in ast.ext:
        if isinstance(ext, c.Decl) and isinstance(ext.type, c.FuncDecl):
            n = ext.name
            if not n or n == "main":
                continue
            sig[n] = _callable_returns_int(ext.type)
    for ext in ast.ext:
        if isinstance(ext, c.FuncDef):
            n = ext.decl.name
            if n == "main":
                continue
            fd = ext.decl.type
            if isinstance(fd, c.FuncDecl):
                sig[n] = _callable_returns_int(fd)
    return sig


def _all_callable_names(ast: c.FileAST) -> frozenset[str]:
    s = set(BUILTIN_KAIROS_PROCS)
    for ext in ast.ext:
        if isinstance(ext, c.Decl) and isinstance(ext.type, c.FuncDecl):
            n = ext.name
            if n and n != "main":
                s.add(n)
        if isinstance(ext, c.FuncDef):
            n = ext.decl.name
            if n != "main":
                s.add(n)
    return frozenset(s)


def _const_int(node: c.Constant) -> int:
    if node.type not in ("int", "long", "unsigned int", "long long"):
        raise MnemoCompileError(f"letterale non int supportato: type={node.type!r}")
    return int(node.value.rstrip("uUlL"), 0)


def _eval_expr(expr: c.Node, ctx: _Ctx) -> tuple[list[Instr], Var | Imm, list[str]]:
    if isinstance(expr, c.Constant):
        return [], Imm(_const_int(expr)), []

    if isinstance(expr, c.ID):
        return [], Var(expr.name), []

    if isinstance(expr, c.UnaryOp):
        if expr.op == "-":
            inner = expr.expr
            if isinstance(inner, c.Constant):
                return [], Imm(-_const_int(inner)), []
            i0, op0, t0 = _eval_expr(inner, ctx)
            t = ctx.fresh_temp()
            ins = i0 + [ISubEq(t, op0)]
            return ins, Var(t), t0 + [t]
        raise MnemoCompileError(f"operatore unario non supportato: {expr.op!r}")

    if isinstance(expr, c.BinaryOp):
        if expr.op in ("+", "-"):
            i1, o1, tm1 = _eval_expr(expr.left, ctx)
            i2, o2, tm2 = _eval_expr(expr.right, ctx)
            t = ctx.fresh_temp()
            if expr.op == "+":
                ins = i1 + i2 + [IAddEq(t, o1), IAddEq(t, o2)]
            else:
                ins = i1 + i2 + [IAddEq(t, o1), ISubEq(t, o2)]
            return ins, Var(t), tm1 + tm2 + [t]
        if expr.op == "*":
            pa, a_name, ca = _eval_to_arg_var(expr.left, ctx)
            pb, b_name, cb = _eval_to_arg_var(expr.right, ctx)
            t = ctx.fresh_temp()
            pre = pa + pb + [ICall("__mn_mul_into", [t, a_name, b_name])]
            post = [IHistPush(ctx.scratch, x) for x in reversed(ca + cb)]
            if ca or cb:
                ctx.use_scratch = True
            return pre + post, Var(t), [t]
        if expr.op == "/":
            pa, va, ca = _eval_to_arg_var(expr.left, ctx)
            pb, vb, cb = _eval_to_arg_var(expr.right, ctx)
            t_a = ctx.fresh_temp()
            t_q = ctx.fresh_temp()
            t_r = ctx.fresh_temp()
            pre = (
                pa
                + pb
                + [IHistPush(ctx.hist, t_a), IAddEq(t_a, Var(va))]
                + [ICall("__mn_divmod_nonneg", [t_a, vb, t_q, t_r])]
            )
            post = [IHistPush(ctx.scratch, x) for x in reversed(ca + cb + [t_r, t_a])]
            ctx.use_hist = True
            ctx.use_scratch = True
            return pre + post, Var(t_q), [t_q]
        if expr.op == "%":
            pa, va, ca = _eval_to_arg_var(expr.left, ctx)
            pb, vb, cb = _eval_to_arg_var(expr.right, ctx)
            t_a = ctx.fresh_temp()
            t_r = ctx.fresh_temp()
            pre = (
                pa
                + pb
                + [IHistPush(ctx.hist, t_a), IAddEq(t_a, Var(va))]
                + [ICall("__mn_mod_nonneg", [t_a, vb, t_r])]
            )
            post = [IHistPush(ctx.scratch, x) for x in reversed(ca + cb + [t_a])]
            ctx.use_hist = True
            ctx.use_scratch = True
            return pre + post, Var(t_r), [t_r]
        raise MnemoCompileError(f"operatore binario non supportato: {expr.op!r}")

    if isinstance(expr, c.Cast):
        tt = expr.to_type
        if isinstance(tt, c.TypeDecl) and isinstance(tt.type, c.IdentifierType):
            if _is_scalar_type_names(tt.type.names):
                return _eval_expr(expr.expr, ctx)
        raise MnemoCompileError("cast non supportato")

    if isinstance(expr, c.ExprList):
        if len(expr.exprs) == 1:
            return _eval_expr(expr.exprs[0], ctx)
        raise MnemoCompileError("ExprList con più espressioni non supportato")

    if isinstance(expr, c.FuncCall):
        if not isinstance(expr.name, c.ID):
            raise MnemoCompileError("callee non è un identificatore")
        name = expr.name.name
        if name not in ctx.extern_procs:
            raise MnemoCompileError(
                f"chiamata a {name!r}: dichiarare la funzione (prototipo o definizione)"
            )
        if not ctx.proc_returns_int.get(name, False):
            raise MnemoCompileError(
                f"{name} è void: non usabile come sotto-espressione (usa solo come istruzione)"
            )
        t = ctx.fresh_temp()
        ins = _lower_funccall_with_ret(expr, ctx, t)
        return ins, Var(t), [t]

    raise MnemoCompileError(f"espressione AST non supportata: {type(expr).__name__}")


def _eval_to_arg_var(expr: c.Node, ctx: _Ctx) -> tuple[list[Instr], str, list[str]]:
    i0, op, tm = _eval_expr(expr, ctx)
    if isinstance(op, Imm):
        t = ctx.fresh_temp()
        return i0 + [IConst(t, op.value)], t, tm + [t]
    if isinstance(op, Var):
        if op.name not in ctx.int_locals:
            raise MnemoCompileError(f"operando non dichiarato: {op.name}")
        return i0, op.name, tm
    raise MnemoCompileError("operando non valido")


def _prepare_call_arg(
    expr: c.Node, ctx: _Ctx
) -> tuple[list[Instr], str, list[str]]:
    if isinstance(expr, c.ID):
        if expr.name not in ctx.int_locals:
            raise MnemoCompileError(f"argomento non dichiarato: {expr.name}")
        return [], expr.name, []
    if isinstance(expr, c.Constant):
        t = ctx.fresh_temp()
        return [IConst(t, _const_int(expr))], t, [t]
    i, op, tm = _eval_expr(expr, ctx)
    if isinstance(op, Imm):
        t = ctx.fresh_temp()
        return i + [IConst(t, op.value)], t, tm + [t]
    if isinstance(op, Var):
        if op.name not in ctx.int_locals:
            raise MnemoCompileError(f"argomento non dichiarato: {op.name}")
        return i, op.name, tm
    raise MnemoCompileError("argomento chiamata non supportato")


def _lower_funccall_with_ret(
    node: c.FuncCall, ctx: _Ctx, ret_sink: str | None
) -> list[Instr]:
    if not isinstance(node.name, c.ID):
        raise MnemoCompileError("callee non è un identificatore")
    name = node.name.name
    if name not in ctx.extern_procs:
        raise MnemoCompileError(
            f"chiamata a {name!r}: dichiarare la funzione (prototipo o definizione)"
        )
    wants = ctx.proc_returns_int.get(name, False)
    if wants and ret_sink is None:
        raise MnemoCompileError(f"{name} restituisce un valore: uso interno errato")
    if not wants and ret_sink is not None:
        raise MnemoCompileError(f"{name} è void: non richiede slot di ritorno")
    el = node.args
    exprs = list(el.exprs) if el is not None else []
    pre: list[Instr] = []
    arg_names: list[str] = []
    to_clear: list[str] = []
    for ex in exprs:
        pi, an, tc = _prepare_call_arg(ex, ctx)
        pre.extend(pi)
        arg_names.append(an)
        to_clear.extend(tc)
    if wants:
        assert ret_sink is not None
        arg_names.append(ret_sink)
    if to_clear:
        ctx.use_scratch = True
    post = [IHistPush(ctx.scratch, t) for t in reversed(to_clear)]
    return pre + [ICall(name, arg_names)] + post


def _lower_expr_as_stmt(expr: c.Node, ctx: _Ctx) -> list[Instr]:
    if isinstance(expr, c.Assignment):
        return _lower_stmt(expr, ctx)
    if isinstance(expr, c.FuncCall):
        return _lower_funccall_with_ret(expr, ctx, None)
    if isinstance(expr, c.UnaryOp) and expr.op in ("p++", "p--", "++", "--"):
        if not isinstance(expr.expr, c.ID):
            raise MnemoCompileError("incremento/decremento solo su variabile")
        v = expr.expr.name
        if v not in ctx.int_locals:
            raise MnemoCompileError(f"variabile non dichiarata: {v}")
        delta = 1 if expr.op in ("p++", "++") else -1
        rhs: c.Node
        if delta == 1:
            rhs = c.BinaryOp(
                "+", c.ID(v), c.Constant("int", "1"), expr.coord
            )
        else:
            rhs = c.BinaryOp(
                "-", c.ID(v), c.Constant("int", "1"), expr.coord
            )
        return _lower_assign(v, rhs, ctx)
    raise MnemoCompileError(
        f"espressione non ammessa come istruzione: {type(expr).__name__}"
    )


def _lower_assign(lhs: str, rhs: c.Node, ctx: _Ctx) -> list[Instr]:
    ei, op, temps = _eval_expr(rhs, ctx)
    ctx.use_hist = True
    if temps:
        ctx.use_scratch = True
    out: list[Instr] = ei + [IHistPush(ctx.hist, lhs), IAddEq(lhs, op)]
    for tmp in reversed(temps):
        out.append(IHistPush(ctx.scratch, tmp))
    return out


def _eval_to_var(
    expr: c.Node, ctx: _Ctx
) -> tuple[list[Instr], str, list[str]]:
    ins, op, tm = _eval_expr(expr, ctx)
    if isinstance(op, Imm):
        t = ctx.fresh_temp()
        return ins + [IConst(t, op.value)], t, tm + [t]
    return ins, op.name, tm


def _kairos_atom(expr: c.Node, ctx: _Ctx) -> tuple[list[Instr], str, list[str]]:
    if isinstance(expr, c.Constant):
        return [], str(_const_int(expr)), []
    if isinstance(expr, c.UnaryOp) and expr.op == "-" and isinstance(
        expr.expr, c.Constant
    ):
        return [], str(-_const_int(expr.expr)), []
    if isinstance(expr, c.ID):
        if expr.name not in ctx.int_locals:
            raise MnemoCompileError(
                f"condizione: variabile non dichiarata {expr.name!r}"
            )
        return [], expr.name, []
    return _eval_to_var(expr, ctx)


def _negate_guard(g: tuple[str, CmpOp, str]) -> tuple[str, CmpOp, str]:
    lh, op, rh = g
    return lh, _NEG_CMP[op], rh


def _lower_predicate_simple(
    expr: c.Node, ctx: _Ctx
) -> tuple[list[Instr], tuple[str, CmpOp, str], list[str]]:
    if isinstance(expr, c.UnaryOp) and expr.op == "!":
        pre, g, tm = _lower_predicate_simple(expr.expr, ctx)
        return pre, _negate_guard(g), tm
    if isinstance(expr, c.ID):
        if expr.name not in ctx.int_locals:
            raise MnemoCompileError(f"condizione: variabile non dichiarata {expr.name!r}")
        return [], (expr.name, "!=", "0"), []
    if isinstance(expr, c.Constant):
        v = _const_int(expr)
        if v == 0:
            return [], ("0", "==", "1"), []
        return [], ("0", "==", "0"), []
    if isinstance(expr, c.BinaryOp):
        if expr.op in ("&&", "||"):
            raise MnemoCompileError("&&/||: usa _lower_if_from_expr / _build_truth_incr_lc")
        if expr.op in _CMP_OPS:
            pre_l, lhs_s, tm_l = _kairos_atom(expr.left, ctx)
            pre_r, rhs_s, tm_r = _kairos_atom(expr.right, ctx)
            op = expr.op
            assert op in _NEG_CMP
            tm = tm_l + tm_r
            return pre_l + pre_r, (lhs_s, op, rhs_s), tm  # type: ignore[arg-type]
        pre, vn, tm = _eval_to_var(expr, ctx)
        return pre, (vn, "!=", "0"), tm
    raise MnemoCompileError(
        f"condizione non supportata: {type(expr).__name__}"
    )


def _append_cond_cleanup(
    out: list[Instr], ctx: _Ctx, cond_temps: list[str]
) -> None:
    if not cond_temps:
        return
    ctx.use_scratch = True
    for t in reversed(cond_temps):
        out.append(IHistPush(ctx.scratch, t))


def _truth_lc_incr(ctx: _Ctx, lc: str) -> list[Instr]:
    ctx.use_hist = True
    return [IHistPush(ctx.hist, lc), IAddEq(lc, Imm(1))]


def _lower_if_from_expr(
    expr: c.Node,
    then_instrs: list[Instr],
    else_instrs: list[Instr] | None,
    ctx: _Ctx,
) -> list[Instr]:
    if isinstance(expr, c.BinaryOp) and expr.op == "&&":
        return _lower_if_from_expr(
            expr.left,
            _lower_if_from_expr(expr.right, then_instrs, else_instrs, ctx),
            else_instrs,
            ctx,
        )
    if isinstance(expr, c.BinaryOp) and expr.op == "||":
        right_chain = _lower_if_from_expr(expr.right, then_instrs, else_instrs, ctx)
        return _lower_if_from_expr(expr.left, then_instrs, right_chain, ctx)
    pre, g, tm = _lower_predicate_simple(expr, ctx)
    lh, op, rh = g
    out: list[Instr] = pre + [IIfKairos(lh, op, rh, then_instrs, else_instrs)]
    _append_cond_cleanup(out, ctx, tm)
    return out


def _build_truth_incr_lc(expr: c.Node, lc: str, ctx: _Ctx) -> list[Instr]:
    if isinstance(expr, c.BinaryOp) and expr.op == "&&":
        return _lower_if_from_expr(
            expr.left,
            _build_truth_incr_lc(expr.right, lc, ctx),
            [],
            ctx,
        )
    if isinstance(expr, c.BinaryOp) and expr.op == "||":
        return _lower_if_from_expr(
            expr.left,
            _truth_lc_incr(ctx, lc),
            _build_truth_incr_lc(expr.right, lc, ctx),
            ctx,
        )
    pre, g, tm = _lower_predicate_simple(expr, ctx)
    lh, op, rh = g
    out: list[Instr] = pre + [IIfKairos(lh, op, rh, _truth_lc_incr(ctx, lc), None)]
    _append_cond_cleanup(out, ctx, tm)
    return out


def _build_truth_incr_lc_br(
    expr: c.Node, lc: str, ctx: _Ctx, br_var: str | None
) -> list[Instr]:
    inner = _build_truth_incr_lc(expr, lc, ctx)
    if br_var is None:
        return inner
    return [IIfKairos(br_var, "==", "0", inner, None)]


def _reset_lc_val(lc: str, ctx: _Ctx) -> list[Instr]:
    """lc ∈ {0,1} → 0: tmp=lc*lc, poi lc ← lc-tmp (mai push(hist,lc) prima di leggere lc-tmp)."""
    tmp = ctx.fresh_temp()
    diff = c.BinaryOp("-", c.ID(lc), c.ID(tmp))
    ei, op, tm = _eval_expr(diff, ctx)
    ctx.use_hist = True
    ctx.use_scratch = True
    out: list[Instr] = [
        ICall("__mn_mul_into", [tmp, lc, lc]),
        *ei,
        IHistPush(ctx.hist, lc),
        IAddEq(lc, op),
    ]
    for t in reversed(tm):
        out.append(IHistPush(ctx.scratch, t))
    out.append(IHistPush(ctx.scratch, tmp))
    return out


def _flatten_stmt_to_list(stmt: c.Node) -> list[c.Node]:
    if isinstance(stmt, c.Compound):
        return list(stmt.block_items or [])
    return [stmt]


def _has_break_targeting_loop(stmt: c.Node | None, inside_inner: bool) -> bool:
    if stmt is None:
        return False
    if isinstance(stmt, c.Break):
        return not inside_inner
    if isinstance(stmt, (c.While, c.For, c.DoWhile)):
        return _has_break_targeting_loop(stmt.stmt, True)
    if isinstance(stmt, c.If):
        a = _has_break_targeting_loop(stmt.iftrue, inside_inner)
        b = _has_break_targeting_loop(stmt.iffalse, inside_inner)
        return a or b
    if isinstance(stmt, c.Compound):
        return any(_has_break_targeting_loop(s, inside_inner) for s in stmt.block_items or [])
    if isinstance(stmt, c.Switch):
        return False
    return False


def _has_continue_targeting_loop(stmt: c.Node | None, inside_inner: bool) -> bool:
    if stmt is None:
        return False
    if isinstance(stmt, c.Continue):
        return not inside_inner
    if isinstance(stmt, (c.While, c.For, c.DoWhile)):
        return _has_continue_targeting_loop(stmt.stmt, True)
    if isinstance(stmt, c.If):
        a = _has_continue_targeting_loop(stmt.iftrue, inside_inner)
        b = _has_continue_targeting_loop(stmt.iffalse, inside_inner)
        return a or b
    if isinstance(stmt, c.Compound):
        return any(_has_continue_targeting_loop(s, inside_inner) for s in stmt.block_items or [])
    if isinstance(stmt, c.Switch):
        return False
    return False


def _is_continue_only_stmt(stmt: c.Node | None) -> bool:
    if stmt is None:
        return False
    if isinstance(stmt, c.Continue):
        return True
    if isinstance(stmt, c.Compound):
        items = stmt.block_items or []
        return len(items) == 1 and _is_continue_only_stmt(items[0])
    return False


def _if_continue_only(node: c.If) -> bool:
    return _is_continue_only_stmt(node.iftrue) and node.iffalse is None


def _lower_stmt_list_tail_continue(
    stmts: list[c.Node], ctx: _Ctx, ct_var: str | None
) -> list[Instr]:
    if not stmts:
        return []
    for i, s in enumerate(stmts):
        if isinstance(s, c.Continue):
            if ct_var is None:
                raise MnemoCompileError("continue fuori da loop")
            head = _lower_stmt_list_tail_continue(stmts[:i], ctx, ct_var)
            tail = _lower_stmt_list_tail_continue(stmts[i + 1 :], ctx, ct_var)
            rest = [IIfKairos(ct_var, "==", "0", tail, None)]
            return head + rest
        if isinstance(s, c.If) and _if_continue_only(s):
            if ct_var is None:
                raise MnemoCompileError("continue fuori da loop")
            head = _lower_stmt_list_tail_continue(stmts[:i], ctx, ct_var)
            tail = _lower_stmt_list_tail_continue(stmts[i + 1 :], ctx, ct_var)
            gated = [IIfKairos(ct_var, "==", "0", tail, None)]
            ctx.use_hist = True
            inc = [IHistPush(ctx.hist, ct_var), IAddEq(ct_var, Imm(1))]
            branch = _lower_if_from_expr(s.cond, inc, None, ctx)
            return head + branch + gated
    out: list[Instr] = []
    for s in stmts:
        out.extend(_lower_stmt(s, ctx))
    return out


def _append_maybe_guarded_by_break(
    instrs: list[Instr], br_var: str | None
) -> list[Instr]:
    if br_var is None or not instrs:
        return instrs
    return [IIfKairos(br_var, "==", "0", instrs, None)]


def _lower_next_clause(node: c.Node | None, ctx: _Ctx) -> list[Instr]:
    if node is None:
        return []
    if getattr(c, "ExprStmt", None) is not None and isinstance(node, c.ExprStmt):
        if node.expr is None:
            return []
        return _lower_expr_as_stmt(node.expr, ctx)
    return _lower_expr_as_stmt(node, ctx)


def _lower_while(node: c.While, ctx: _Ctx) -> list[Instr]:
    lc = ctx.fresh_temp()
    cond = node.cond if node.cond is not None else c.Constant("int", "1")
    stmts = _flatten_stmt_to_list(node.stmt)
    need_br = _has_break_targeting_loop(node.stmt, False)
    need_ct = _has_continue_targeting_loop(node.stmt, False)
    br_v = ctx.fresh_temp() if need_br else None
    ct_v = ctx.fresh_temp() if need_ct else None

    ctx.loop_stack.append(_LoopFrame(br_v, ct_v))
    try:
        core = _lower_stmt_list_tail_continue(stmts, ctx, ct_v)
        if need_ct:
            assert ct_v is not None
            core = [ILocalBlock(ct_v, core + _reset_lc_val(ct_v, ctx))]
        recompute = _reset_lc_val(lc, ctx) + _build_truth_incr_lc_br(cond, lc, ctx, br_v)
        body = core + recompute
    finally:
        ctx.loop_stack.pop()

    first_eval = _build_truth_incr_lc_br(cond, lc, ctx, br_v)
    return first_eval + [
        IFromUntilKairos(
            lc,
            "!=",
            "0",
            body,
            lc,
            "==",
            "0",
        )
    ]


def _lower_dowhile(node: c.DoWhile, ctx: _Ctx) -> list[Instr]:
    lc = ctx.fresh_temp()
    cond = node.cond if node.cond is not None else c.Constant("int", "1")
    stmts = _flatten_stmt_to_list(node.stmt)
    need_br = _has_break_targeting_loop(node.stmt, False)
    need_ct = _has_continue_targeting_loop(node.stmt, False)
    br_v = ctx.fresh_temp() if need_br else None
    ct_v = ctx.fresh_temp() if need_ct else None

    ctx.loop_stack.append(_LoopFrame(br_v, ct_v))
    try:
        core = _lower_stmt_list_tail_continue(stmts, ctx, ct_v)
        if need_ct:
            assert ct_v is not None
            core = [ILocalBlock(ct_v, core + _reset_lc_val(ct_v, ctx))]
        recompute = _reset_lc_val(lc, ctx) + _build_truth_incr_lc_br(cond, lc, ctx, br_v)
        body = core + recompute
    finally:
        ctx.loop_stack.pop()

    return [
        IFromUntilKairos(
            "0",
            "==",
            "0",
            body,
            lc,
            "==",
            "0",
        )
    ]


def _lower_for_init(init: c.Node | None, ctx: _Ctx) -> list[Instr]:
    if init is None:
        return []
    if isinstance(init, c.DeclList):
        out: list[Instr] = []
        for decl in init.decls:
            out.extend(_lower_stmt(decl, ctx))
        return out
    if isinstance(init, (c.Decl, c.Assignment)):
        return _lower_stmt(init, ctx)
    if isinstance(init, c.FuncCall):
        return _lower_stmt(init, ctx)
    if getattr(c, "ExprStmt", None) is not None and isinstance(init, c.ExprStmt):
        if init.expr is None:
            return []
        return _lower_expr_as_stmt(init.expr, ctx)
    raise MnemoCompileError(f"for-init non supportato: {type(init).__name__}")


def _lower_for(node: c.For, ctx: _Ctx) -> list[Instr]:
    pre = _lower_for_init(node.init, ctx)
    cond = node.cond if node.cond is not None else c.Constant("int", "1")
    if isinstance(node.stmt, c.Compound):
        body_only = list(node.stmt.block_items or [])
    else:
        body_only = [node.stmt]

    lc = ctx.fresh_temp()
    need_br = _has_break_targeting_loop(node.stmt, False)
    need_ct = _has_continue_targeting_loop(node.stmt, False)
    br_v = ctx.fresh_temp() if need_br else None
    ct_v = ctx.fresh_temp() if need_ct else None
    next_instrs = _lower_next_clause(node.next, ctx)
    next_part = _append_maybe_guarded_by_break(next_instrs, br_v)

    ctx.loop_stack.append(_LoopFrame(br_v, ct_v))
    try:
        core = _lower_stmt_list_tail_continue(body_only, ctx, ct_v)
        if need_ct:
            assert ct_v is not None
            core = [ILocalBlock(ct_v, core + _reset_lc_val(ct_v, ctx))]
        core = core + next_part
        recompute = _reset_lc_val(lc, ctx) + _build_truth_incr_lc_br(cond, lc, ctx, br_v)
        body = core + recompute
    finally:
        ctx.loop_stack.pop()

    first_eval = _build_truth_incr_lc_br(cond, lc, ctx, br_v)
    return pre + first_eval + [
        IFromUntilKairos(
            lc,
            "!=",
            "0",
            body,
            lc,
            "==",
            "0",
        )
    ]


def _lower_substmt(stmt: c.Node | None, ctx: _Ctx) -> list[Instr]:
    if stmt is None:
        return []
    if isinstance(stmt, c.Compound):
        out: list[Instr] = []
        for sub in stmt.block_items or []:
            out.extend(_lower_stmt(sub, ctx))
        return out
    return _lower_stmt(stmt, ctx)


def _lower_if(node: c.If, ctx: _Ctx) -> list[Instr]:
    then_instrs = _lower_substmt(node.iftrue, ctx)
    else_instrs: list[Instr] | None = (
        _lower_substmt(node.iffalse, ctx) if node.iffalse is not None else None
    )
    return _lower_if_from_expr(node.cond, then_instrs, else_instrs, ctx)


def _sanitize_case_stmts(stmts: list[c.Node], case_label: str) -> list[c.Node]:
    if not stmts:
        return []
    for i, s in enumerate(stmts):
        if isinstance(s, c.Break):
            if i != len(stmts) - 1:
                raise MnemoCompileError(
                    f"switch {case_label}: break solo in coda al case"
                )
            return list(stmts[:-1])
    raise MnemoCompileError(
        f"switch {case_label}: ogni case/default deve terminare con break "
        f"(fall-through non supportato)"
    )


def _parse_switch_cases(
    items: list[c.Node],
) -> list[tuple[str, list[c.Node]]]:
    cases: list[tuple[str, list[c.Node]]] = []
    for it in items:
        if isinstance(it, c.Case):
            if not isinstance(it.expr, c.Constant):
                raise MnemoCompileError("switch: case richiede costante intera")
            lab = str(_const_int(it.expr))
            cases.append((lab, _sanitize_case_stmts(it.stmts, f"case {lab}")))
        elif isinstance(it, c.Default):
            cases.append(
                ("default", _sanitize_case_stmts(it.stmts, "default"))
            )
        else:
            raise MnemoCompileError(
                "nel corpo switch sono ammessi solo case e default"
            )
    for i, (v, _) in enumerate(cases):
        if v == "default" and i != len(cases) - 1:
            raise MnemoCompileError("switch: default deve essere l'ultimo branch")
    return cases


def _switch_chain(
    disc: str,
    cases: list[tuple[str, list[c.Node]]],
    ctx: _Ctx,
    idx: int,
) -> list[Instr]:
    if idx >= len(cases):
        return []
    val, stmts = cases[idx]
    body: list[Instr] = []
    for s in stmts:
        body.extend(_lower_stmt(s, ctx))
    if val == "default":
        return body
    rest = _switch_chain(disc, cases, ctx, idx + 1)
    if not rest:
        return [IIfKairos(disc, "==", val, body, None)]
    return [IIfKairos(disc, "==", val, body, rest)]


def _lower_switch(node: c.Switch, ctx: _Ctx) -> list[Instr]:
    if not isinstance(node.stmt, c.Compound):
        raise MnemoCompileError("switch: il corpo deve essere { ... }")
    pre_d, disc_var, tm_d = _kairos_atom(node.cond, ctx)
    cases = _parse_switch_cases(node.stmt.block_items or [])
    if not cases:
        out = list(pre_d)
        _append_cond_cleanup(out, ctx, tm_d)
        return out
    chain = _switch_chain(disc_var, cases, ctx, 0)
    out = pre_d + chain
    _append_cond_cleanup(out, ctx, tm_d)
    return out


def _lower_stmt(node: c.Node, ctx: _Ctx) -> list[Instr]:
    if isinstance(node, c.EmptyStatement):
        return []

    if isinstance(node, c.Decl):
        name = _scalar_decl_name(node)
        if name is None:
            raise MnemoCompileError(f"dichiarazione non supportata: {type(node.type).__name__}")
        if name in ctx.int_locals:
            raise MnemoCompileError(f"ridichiarazione: {name}")
        ctx.int_locals.add(name)
        ctx.decl_order.append(name)
        if node.init is None:
            return []
        if isinstance(node.init, c.InitList):
            raise MnemoCompileError("init struct/array non supportato")
        return _lower_assign(name, node.init, ctx)

    if isinstance(node, c.Assignment):
        if not isinstance(node.lvalue, c.ID):
            raise MnemoCompileError("lvalue non-ID non supportato")
        lhs = node.lvalue.name
        if lhs not in ctx.int_locals:
            raise MnemoCompileError(f"assegnamento a variabile non dichiarata: {lhs}")
        if node.op == "=":
            return _lower_assign(lhs, node.rvalue, ctx)
        compound = {"+=": "+", "-=": "-", "*=": "*", "/=": "/", "%=": "%"}
        if node.op in compound:
            rhs = c.BinaryOp(
                compound[node.op], c.ID(lhs), node.rvalue, node.coord
            )
            return _lower_assign(lhs, rhs, ctx)
        raise MnemoCompileError(f"assegnamento con {node.op!r} non supportato")

    if getattr(c, "ExprStmt", None) is not None and isinstance(node, c.ExprStmt):
        if node.expr is None:
            return []
        return _lower_expr_as_stmt(node.expr, ctx)

    if isinstance(node, c.UnaryOp):
        return _lower_expr_as_stmt(node, ctx)

    if isinstance(node, c.FuncCall):
        if not isinstance(node.name, c.ID):
            raise MnemoCompileError("callee non è un identificatore")
        nm = node.name.name
        if ctx.proc_returns_int.get(nm, False):
            t = ctx.fresh_temp()
            return _lower_funccall_with_ret(node, ctx, t)
        return _lower_funccall_with_ret(node, ctx, None)

    if isinstance(node, c.If):
        return _lower_if(node, ctx)

    if isinstance(node, c.While):
        return _lower_while(node, ctx)

    if isinstance(node, c.DoWhile):
        return _lower_dowhile(node, ctx)

    if isinstance(node, c.Switch):
        return _lower_switch(node, ctx)

    if isinstance(node, c.Break):
        if not ctx.loop_stack:
            raise MnemoCompileError(
                "break fuori da loop (in switch è consentito solo come ultima istruzione di un case)"
            )
        fr = ctx.loop_stack[-1]
        if fr.br_var is None:
            raise MnemoCompileError(
                "break non collegato a un ciclo (es. solo switch annidato)"
            )
        ctx.use_hist = True
        return [IHistPush(ctx.hist, fr.br_var), IAddEq(fr.br_var, Imm(1))]

    if isinstance(node, c.Continue):
        if not ctx.loop_stack:
            raise MnemoCompileError("continue fuori da loop")
        fr = ctx.loop_stack[-1]
        if fr.ct_var is None:
            raise MnemoCompileError("continue: errore interno")
        ctx.use_hist = True
        return [IHistPush(ctx.hist, fr.ct_var), IAddEq(fr.ct_var, Imm(1))]

    if isinstance(node, c.For):
        return _lower_for(node, ctx)

    if isinstance(node, c.Return):
        if ctx.is_main:
            if node.expr is None:
                return [IReturn()]
            if isinstance(node.expr, c.Constant) and _const_int(node.expr) == 0:
                return [IReturn()]
            return [IComment("return main: valore ignorato"), IReturn()]
        if ctx.returns_int:
            if node.expr is None:
                raise MnemoCompileError("return senza espressione in funzione non-void")
            assert ctx.ret_var is not None
            ei, op, temps = _eval_expr(node.expr, ctx)
            ctx.use_hist = True
            if temps:
                ctx.use_scratch = True
            out: list[Instr] = ei + [
                IHistPush(ctx.hist, ctx.ret_var),
                IAddEq(ctx.ret_var, op),
            ]
            for tmp in reversed(temps):
                out.append(IHistPush(ctx.scratch, tmp))
            out.append(IReturn())
            return out
        if node.expr is not None:
            raise MnemoCompileError("return con valore in funzione void")
        return [IReturn()]

    if isinstance(node, c.Compound):
        out: list[Instr] = []
        for sub in node.block_items or []:
            out.extend(_lower_stmt(sub, ctx))
        return out

    raise MnemoCompileError(f"istruzione non supportata: {type(node).__name__}")


def _is_int_main(ext: c.Node) -> bool:
    if not isinstance(ext, c.FuncDef):
        return False
    if ext.decl.name != "main":
        return False
    fd = ext.decl.type
    if not isinstance(fd, c.FuncDecl):
        return False
    rt = fd.type
    if isinstance(rt, c.TypeDecl) and isinstance(rt.type, c.IdentifierType):
        return rt.type.names == ["int"]
    return False


def _find_main(ast: c.FileAST) -> c.FuncDef | None:
    for ext in ast.ext:
        if _is_int_main(ext):
            return ext
    return None


def infer_auto_lib_files(ast: c.FileAST) -> list[str]:
    needed: set[str] = set()

    def visit(node: object) -> None:
        if node is None:
            return
        if isinstance(node, (c.While, c.DoWhile, c.For)):
            needed.add("mul.kairos")
        if isinstance(node, c.BinaryOp):
            if node.op == "*":
                needed.add("mul.kairos")
            elif node.op == "/":
                needed.add("helpers.kairos")
                needed.add("divmod.kairos")
            elif node.op == "%":
                needed.add("helpers.kairos")
                needed.add("mod.kairos")
        if not hasattr(node, "children"):
            return
        for _name, ch in node.children():
            if ch is None:
                continue
            if isinstance(ch, list):
                for item in ch:
                    visit(item)
            else:
                visit(ch)

    for ext in ast.ext:
        visit(ext)

    order = ["helpers.kairos", "mul.kairos", "divmod.kairos", "mod.kairos"]
    return [name for name in order if name in needed]


def infer_lib_files_from_calls(
    ast: c.FileAST, proc_to_file: dict[str, str]
) -> list[str]:
    """
    Include i file `lib/*.kairos` che definiscono procedure invocate dal C
    (chiamate a nomi non definiti nel .c e non built-in Mnemo).
    """
    defined: set[str] = set()
    for ext in ast.ext:
        if isinstance(ext, c.FuncDef) and ext.decl.name:
            defined.add(ext.decl.name)

    needed: set[str] = set()

    def visit(node: object) -> None:
        if isinstance(node, c.FuncCall) and isinstance(node.name, c.ID):
            name = node.name.name
            if (
                name
                and name not in defined
                and name not in BUILTIN_KAIROS_PROCS
            ):
                libf = proc_to_file.get(name)
                if libf is not None:
                    needed.add(libf)
        if not hasattr(node, "children"):
            return
        for _n, ch in node.children():
            if ch is None:
                continue
            if isinstance(ch, list):
                for item in ch:
                    visit(item)
            else:
                visit(ch)

    for ext in ast.ext:
        visit(ext)

    order = ["helpers.kairos", "mul.kairos", "divmod.kairos", "mod.kairos"]
    head = [n for n in order if n in needed]
    tail = sorted(needed.difference(head))
    return head + tail


def _locals_list(ctx: _Ctx) -> list[tuple[str, str]]:
    locals_list: list[tuple[str, str]] = []
    for n in ctx.decl_order:
        locals_list.append(("int", n))
    for n in sorted(
        (x for x in ctx.int_locals if x.startswith("__mn_e")),
        key=lambda s: int(s[6:]),
    ):
        locals_list.append(("int", n))
    if ctx.use_hist:
        locals_list.append(("stack", ctx.hist))
    if ctx.use_scratch:
        locals_list.append(("stack", ctx.scratch))
    return locals_list


def _lower_user_function(
    fdef: c.FuncDef,
    callable_names: frozenset[str],
    proc_returns_int: dict[str, bool],
) -> Function:
    name = fdef.decl.name
    fd = fdef.decl.type
    if not isinstance(fd, c.FuncDecl):
        raise MnemoCompileError("definizione funzione malformata")
    body = fdef.body
    if body is None or not isinstance(body, c.Compound):
        raise MnemoCompileError("corpo funzione non è un blocco { ... }")

    ret_int = proc_returns_int.get(name, False)
    params = _func_param_names(fd)
    param_order = params + ([MN_RET] if ret_int else [])

    ctx = _Ctx(
        extern_procs=callable_names,
        proc_returns_int=proc_returns_int,
        int_locals=set(param_order),
        decl_order=[],
        param_names=frozenset(param_order),
        is_main=False,
        returns_int=ret_int,
        ret_var=MN_RET if ret_int else None,
    )

    instrs: list[Instr] = []
    for item in body.block_items or []:
        instrs.extend(_lower_stmt(item, ctx))

    return Function(
        name=name,
        params=[("int", p) for p in param_order],
        locals=_locals_list(ctx),
        blocks=[Block("entry", [IComment(f"funzione C {name}")] + instrs)],
    )


def lower_file_to_program(ast: c.FileAST, *, main_argc: int = 0) -> Program:
    main_fn = _find_main(ast)
    if main_fn is None:
        raise MnemoCompileError("nessuna funzione int main(...) trovata")

    body = main_fn.body
    if body is None or not isinstance(body, c.Compound):
        raise MnemoCompileError("corpo main non è un blocco { ... }")

    mfd = main_fn.decl.type
    if not isinstance(mfd, c.FuncDecl):
        raise MnemoCompileError("main: firma malformata")
    main_param_setup = _main_locals_from_fd(mfd)

    proc_returns_int = _merge_proc_returns_int(ast)
    callable_names = _all_callable_names(ast)

    user_fns: list[Function] = []
    for ext in ast.ext:
        if isinstance(ext, c.FuncDef) and ext.decl.name != "main":
            user_fns.append(_lower_user_function(ext, callable_names, proc_returns_int))

    ctx = _Ctx(
        extern_procs=callable_names,
        proc_returns_int=proc_returns_int,
        is_main=True,
    )
    for name, _role in main_param_setup:
        ctx.int_locals.add(name)
        ctx.decl_order.append(name)

    instrs: list[Instr] = []
    for name, role in main_param_setup:
        if role == "argc":
            instrs.append(IConst(name, main_argc))
        else:
            instrs.append(IConst(name, 0))

    for item in body.block_items or []:
        instrs.extend(_lower_stmt(item, ctx))

    main_ir = Function(
        name="main",
        params=[],
        locals=_locals_list(ctx),
        blocks=[Block("entry", [IComment("generato da Mnemo da C")] + instrs)],
    )

    return Program(functions=user_fns + [main_ir])
