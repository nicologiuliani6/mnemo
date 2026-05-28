"""C → .kairos: parse, lower, emit, prelude lib/."""

from __future__ import annotations

from mnemo.c_lower import (
    PTHREAD_ABI_TWO_REGION_PAR,
    _convert_kr_to_ansi,
    _hoist_compound_literals_in_ast,
    _hoist_static_locals,
    _hoist_string_literal_call_args_in_ast,
    _name_anonymous_structs_unions,
    infer_auto_lib_files,
    infer_lib_files_from_calls,
    lower_file_to_program,
)
from mnemo.inline_user import maybe_inline_user_functions
from mnemo.layout_collect import compute_program_mem_layout
from mnemo.par_shared_mutex_check import check_par_shared_mutex_discipline
from mnemo.c_parse import parse_c
from mnemo.emit_kairos import emit_program
from mnemo.errors import MnemoCompileError
from mnemo.ir import (
    Block,
    Function,
    ICall,
    IIfKairos,
    IFromUntilKairos,
    ILocalBlock,
    IPar,
    Instr,
    IUncall,
    Program,
)
from mnemo.prelude import (
    lib_procedure_index,
    load_prelude_kairos,
    parse_mnemo_main_argc,
    parse_mnemo_skip_par_shared_mutex_check,
)
from mnemo.ptr_pool_kairos import PTR_POOL_MAX
import pycparser.c_ast as c


def _transform_return_in_loop(ast: c.FileAST) -> None:
    """Rewrite `return E;` dentro for/while/do-while body via return-flag.

    Trasformazione:
        int f(...) {
            pre_stmts;
            for (init; cond; next) {
                body_with_returns;
            }
            return E_late;
        }

    diventa:
        int __mn_rv5_k = 0;
        int __mn_rf5_k = 0;
        pre_stmts;
        for (init; cond; next) {
            if (!__mn_rf5_k) {
                body_with_returns_to_flag_assignments;
            }
        }
        if (!__mn_rf5_k) {
            __mn_rv5_k = E_late;
        }
        return __mn_rv5_k;

    Ogni `return E;` nel loop body diventa `{ __mn_rv5_k = E; __mn_rf5_k = 1; }`.
    Il loop esegue tutte le iterazioni (no early break), ma il body è skippato
    dopo che il flag è alzato. Il return finale viene anche skippato.

    Restrizioni:
    - L'ultima stmt deve essere `return E;`.
    - I return interni devono essere dentro UN solo loop (no nested return).
    - Niente return in stmt fra l'ultimo loop e il return finale.
    """
    counter = [0]

    def _fresh_pair() -> tuple[str, str]:
        counter[0] += 1
        return f"__mn_rv5_{counter[0]}", f"__mn_rf5_{counter[0]}"

    def _has_return(node: c.Node | None) -> bool:
        if node is None:
            return False
        for sub in _iter_c_nodes(node):
            if isinstance(sub, c.Return):
                return True
        return False

    def _replace_returns_with_flag(
        node: c.Node | None, rv: str, rf: str
    ) -> c.Node | None:
        if node is None:
            return None
        if isinstance(node, c.Return):
            if node.expr is None:
                return c.Compound(block_items=[
                    c.Assignment(op="=", lvalue=c.ID(name=rf),
                                 rvalue=c.Constant(type="int", value="1")),
                ])
            return c.Compound(block_items=[
                c.Assignment(op="=", lvalue=c.ID(name=rv), rvalue=node.expr),
                c.Assignment(op="=", lvalue=c.ID(name=rf),
                             rvalue=c.Constant(type="int", value="1")),
            ])
        if isinstance(node, c.Compound):
            new_items = []
            for s in node.block_items or []:
                ns = _replace_returns_with_flag(s, rv, rf)
                if ns is not None:
                    new_items.append(ns)
            return c.Compound(block_items=new_items)
        if isinstance(node, c.If):
            return c.If(
                cond=node.cond,
                iftrue=_replace_returns_with_flag(node.iftrue, rv, rf),
                iffalse=_replace_returns_with_flag(node.iffalse, rv, rf),
            )
        if isinstance(node, c.While):
            return c.While(
                cond=node.cond,
                stmt=_replace_returns_with_flag(node.stmt, rv, rf),
            )
        if isinstance(node, c.DoWhile):
            return c.DoWhile(
                cond=node.cond,
                stmt=_replace_returns_with_flag(node.stmt, rv, rf),
            )
        if isinstance(node, c.For):
            return c.For(
                init=node.init, cond=node.cond, next=node.next,
                stmt=_replace_returns_with_flag(node.stmt, rv, rf),
            )
        if isinstance(node, c.Switch):
            return c.Switch(
                cond=node.cond,
                stmt=_replace_returns_with_flag(node.stmt, rv, rf),
            )
        if isinstance(node, c.Case):
            return c.Case(
                expr=node.expr,
                stmts=[
                    _replace_returns_with_flag(x, rv, rf)
                    for x in (node.stmts or [])
                ],
            )
        if isinstance(node, c.Default):
            return c.Default(
                stmts=[
                    _replace_returns_with_flag(x, rv, rf)
                    for x in (node.stmts or [])
                ],
            )
        return node

    def _is_void_func(fd: c.FuncDef) -> bool:
        fdt = fd.decl.type
        if not isinstance(fdt, c.FuncDecl):
            return False
        rt = fdt.type
        if isinstance(rt, c.TypeDecl) and isinstance(rt.type, c.IdentifierType):
            return rt.type.names == ["void"]
        return False

    for ext in ast.ext or []:
        if not isinstance(ext, c.FuncDef):
            continue
        if ext.body is None or not isinstance(ext.body, c.Compound):
            continue
        items = list(ext.body.block_items or [])
        if not items:
            continue
        last = items[-1]
        is_void = _is_void_func(ext)
        has_trailing_return = isinstance(last, c.Return) and last.expr is not None
        if not has_trailing_return and not is_void:
            continue
        if len(items) < 2 and not is_void:
            continue
        # Per void senza trailing return: trattiamo come se trailing return None.
        last_is_loop_only = is_void and not has_trailing_return
        scan_items = items[:-1] if has_trailing_return else items
        # Verifica che ci sia ALMENO un loop con return e che NON ci siano
        # return fuori da loop fra gli stmts.
        loops_with_return: list[int] = []
        for k, s in enumerate(scan_items):
            if isinstance(s, (c.For, c.While, c.DoWhile)):
                if _has_return(s.stmt):
                    loops_with_return.append(k)
            else:
                if _has_return(s):
                    loops_with_return = []
                    break
        if not loops_with_return:
            continue
        rv_name, rf_name = _fresh_pair()
        rv_decl = c.Decl(
            name=rv_name,
            quals=[], align=[], storage=[], funcspec=[],
            type=c.TypeDecl(
                declname=rv_name, quals=[], align=None,
                type=c.IdentifierType(names=["int"]),
            ),
            init=c.Constant(type="int", value="0"),
            bitsize=None,
        )
        rf_decl = c.Decl(
            name=rf_name,
            quals=[], align=[], storage=[], funcspec=[],
            type=c.TypeDecl(
                declname=rf_name, quals=[], align=None,
                type=c.IdentifierType(names=["int"]),
            ),
            init=c.Constant(type="int", value="0"),
            bitsize=None,
        )
        new_items: list[c.Node] = [rv_decl, rf_decl]
        for k, s in enumerate(scan_items):
            if k in loops_with_return:
                inner = _replace_returns_with_flag(s.stmt, rv_name, rf_name)
                guard = c.UnaryOp(op="!", expr=c.ID(name=rf_name))
                wrapped_body = c.If(
                    cond=guard,
                    iftrue=inner if isinstance(inner, c.Compound)
                    else c.Compound(block_items=[inner] if inner else []),
                    iffalse=None,
                )
                # Estendi loop guard con `&& !flag` per uscire dopo che il
                # return interno ha alzato la flag (next iter cond=false).
                guard_and_noflag = c.BinaryOp(
                    op="&&",
                    left=s.cond if s.cond is not None
                    else c.Constant(type="int", value="1"),
                    right=c.UnaryOp(op="!", expr=c.ID(name=rf_name)),
                )
                if isinstance(s, c.For):
                    new_loop = c.For(
                        init=s.init, cond=guard_and_noflag, next=s.next,
                        stmt=c.Compound(block_items=[wrapped_body]),
                    )
                elif isinstance(s, c.While):
                    new_loop = c.While(
                        cond=guard_and_noflag,
                        stmt=c.Compound(block_items=[wrapped_body]),
                    )
                else:
                    new_loop = c.DoWhile(
                        cond=guard_and_noflag,
                        stmt=c.Compound(block_items=[wrapped_body]),
                    )
                new_items.append(new_loop)
            else:
                new_items.append(s)
        if has_trailing_return:
            late_assign = c.Assignment(
                op="=", lvalue=c.ID(name=rv_name), rvalue=last.expr,
            )
            late_guard = c.If(
                cond=c.UnaryOp(op="!", expr=c.ID(name=rf_name)),
                iftrue=c.Compound(block_items=[late_assign]),
                iffalse=None,
            )
            new_items.append(late_guard)
            new_items.append(c.Return(expr=c.ID(name=rv_name)))
        ext.body.block_items = new_items


def _transform_hoist_unsafe_if_conds(ast: c.FileAST) -> None:
    """Hoist `if (E) S` cond in fresh int quando S muta variabili usate in E.

    La Kairos VM richiede che la condizione `fi c` post-branch coincida con `if c`
    pre-branch. Se S muta variabili in E (es. `i = i + 1` con cond `i == 2`)
    il check fi fallisce con "IF/FI non reversibile". Workaround tipico: lo
    sviluppatore introduce `int g = i==2; if (g) ...`. Questo pass automatizza:

        if (E) S1 else S2  →  int __mn_gif_k = (E); if (__mn_gif_k) S1 else S2

    quando i nomi liberi in E intersecano i nomi assegnati in S1 ∪ S2.
    """
    counter = [0]

    def _fresh() -> str:
        counter[0] += 1
        return f"__mn_gif_{counter[0]}"

    def _ids_in(node: c.Node | None) -> set[str]:
        out: set[str] = set()
        if node is None:
            return out
        for sub in _iter_c_nodes(node):
            if isinstance(sub, c.ID):
                out.add(sub.name)
        return out

    def _lvalue_id_name(lv: c.Node | None) -> str | None:
        if isinstance(lv, c.ID):
            return lv.name
        return None

    def _writes_in(node: c.Node | None) -> set[str]:
        out: set[str] = set()
        if node is None:
            return out
        for sub in _iter_c_nodes(node):
            if isinstance(sub, c.Assignment):
                nm = _lvalue_id_name(sub.lvalue)
                if nm is not None:
                    out.add(nm)
            if isinstance(sub, c.UnaryOp) and sub.op in ("++", "--", "p++", "p--"):
                nm = _lvalue_id_name(sub.expr)
                if nm is not None:
                    out.add(nm)
        return out

    def _wrap_block(items: list[c.Node]) -> list[c.Node]:
        return [_rewrite_stmt(s) for s in items]

    def _rewrite_stmt(s: c.Node) -> c.Node:
        if isinstance(s, c.If):
            new_t = _rewrite_stmt(s.iftrue) if s.iftrue is not None else None
            new_f = _rewrite_stmt(s.iffalse) if s.iffalse is not None else None
            cond_ids = _ids_in(s.cond)
            body_writes = _writes_in(new_t) | _writes_in(new_f)
            if cond_ids & body_writes:
                g_name = _fresh()
                g_decl = c.Decl(
                    name=g_name,
                    quals=[], align=[], storage=[], funcspec=[],
                    type=c.TypeDecl(
                        declname=g_name, quals=[], align=None,
                        type=c.IdentifierType(names=["int"]),
                    ),
                    init=s.cond,
                    bitsize=None,
                )
                new_if = c.If(
                    cond=c.ID(name=g_name),
                    iftrue=new_t,
                    iffalse=new_f,
                )
                return c.Compound(block_items=[g_decl, new_if])
            return c.If(cond=s.cond, iftrue=new_t, iffalse=new_f)
        if isinstance(s, c.Compound):
            items = s.block_items or []
            return c.Compound(block_items=_wrap_block(list(items)))
        if isinstance(s, c.While):
            return c.While(cond=s.cond, stmt=_rewrite_stmt(s.stmt))
        if isinstance(s, c.DoWhile):
            return c.DoWhile(cond=s.cond, stmt=_rewrite_stmt(s.stmt))
        if isinstance(s, c.For):
            return c.For(
                init=s.init, cond=s.cond, next=s.next,
                stmt=_rewrite_stmt(s.stmt),
            )
        if isinstance(s, c.Switch):
            return c.Switch(cond=s.cond, stmt=_rewrite_stmt(s.stmt))
        if isinstance(s, c.Case):
            return c.Case(
                expr=s.expr,
                stmts=[_rewrite_stmt(x) for x in (s.stmts or [])],
            )
        if isinstance(s, c.Default):
            return c.Default(stmts=[_rewrite_stmt(x) for x in (s.stmts or [])])
        return s

    for ext in ast.ext or []:
        if not isinstance(ext, c.FuncDef):
            continue
        if ext.body is None or not isinstance(ext.body, c.Compound):
            continue
        items = ext.body.block_items or []
        ext.body.block_items = _wrap_block(list(items))


def _transform_general_early_returns(ast: c.FileAST) -> None:
    """Rewrite `stmt1; ...; if (c) return E1; ...; return E2;` → single-return.

    Generalizzazione di `_transform_early_return_if_then_return` che ammette
    qualsiasi numero di statement non-return PRIMA dell'`if (c) return E;`.
    Trasformazione:

        s1; ...; sk; if (c) return E1; t1; ...; tm; return E2;

    diventa (con `__mn_g_k` snapshot stabile di `c`, `__mn_rv4_k` slot return):

        s1; ...; sk;
        int __mn_g_k = (c);
        int __mn_rv4_k = 0;
        if (__mn_g_k) __mn_rv4_k = E1;
        else { t1; ...; tm; __mn_rv4_k = E2; }
        return __mn_rv4_k;

    Snapshot necessario perché il ramo else può mutare le variabili usate in
    `c`, rompendo la condizione `fi` reversibile della VM Kairos.
    Si applica ricorsivamente sul ramo else con suffisso fresco per gestire
    cascade. Restrizione: niente early-return dentro loop/switch (TODO).
    """
    counter = [0]

    def _fresh(prefix: str) -> str:
        counter[0] += 1
        return f"{prefix}_{counter[0]}"

    def is_if_with_return_then_else_less(s: c.Node) -> bool:
        if not isinstance(s, c.If):
            return False
        if s.iffalse is not None:
            return False
        t = s.iftrue
        if isinstance(t, c.Compound):
            its = t.block_items or []
            if len(its) == 1 and isinstance(its[0], c.Return) and its[0].expr is not None:
                return True
            return False
        return isinstance(t, c.Return) and t.expr is not None

    def extract_then_return_expr(s: c.If) -> c.Node:
        t = s.iftrue
        if isinstance(t, c.Compound):
            return (t.block_items or [])[0].expr
        return t.expr

    def has_any_return(node: c.Node) -> bool:
        for sub in _iter_c_nodes(node):
            if isinstance(sub, c.Return):
                return True
        return False

    def rewrite_items(items: list[c.Node]) -> list[c.Node] | None:
        if not items:
            return None
        last = items[-1]
        if not (isinstance(last, c.Return) and last.expr is not None):
            return None
        early_idx = -1
        for k, st in enumerate(items[:-1]):
            if is_if_with_return_then_else_less(st):
                early_idx = k
                break
        if early_idx < 0:
            return None
        pre = items[:early_idx]
        for s in pre:
            if has_any_return(s):
                return None
        if_node = items[early_idx]
        post_mid = items[early_idx + 1:-1]
        for s in post_mid:
            if has_any_return(s):
                return None
        rv_name = _fresh("__mn_rv4")
        g_name = _fresh("__mn_g")
        early_expr = extract_then_return_expr(if_node)
        early_assign = c.Assignment(
            op="=", lvalue=c.ID(name=rv_name), rvalue=early_expr,
        )
        late_assign = c.Assignment(
            op="=", lvalue=c.ID(name=rv_name), rvalue=last.expr,
        )
        sub = rewrite_items(list(post_mid) + [c.Return(expr=last.expr)])
        if sub is not None:
            # Sub-rewrite gestisce il proprio rv_name/return; inietta
            # __mn_rv4_k = sub.return.expr al posto della return finale.
            sub_ret = sub[-1]
            assert isinstance(sub_ret, c.Return)
            inner_items = list(sub[:-1]) + [
                c.Assignment(op="=", lvalue=c.ID(name=rv_name), rvalue=sub_ret.expr),
            ]
            else_items = inner_items
        else:
            else_items = list(post_mid) + [late_assign]
        new_if = c.If(
            cond=c.ID(name=g_name),
            iftrue=early_assign,
            iffalse=c.Compound(block_items=else_items),
        )
        g_decl = c.Decl(
            name=g_name,
            quals=[], align=[], storage=[], funcspec=[],
            type=c.TypeDecl(
                declname=g_name, quals=[], align=None,
                type=c.IdentifierType(names=["int"]),
            ),
            init=if_node.cond,
            bitsize=None,
        )
        rv_decl = c.Decl(
            name=rv_name,
            quals=[], align=[], storage=[], funcspec=[],
            type=c.TypeDecl(
                declname=rv_name, quals=[], align=None,
                type=c.IdentifierType(names=["int"]),
            ),
            init=c.Constant(type="int", value="0"),
            bitsize=None,
        )
        return list(pre) + [g_decl, rv_decl, new_if, c.Return(expr=c.ID(name=rv_name))]

    for ext in ast.ext or []:
        if not isinstance(ext, c.FuncDef):
            continue
        if ext.body is None or not isinstance(ext.body, c.Compound):
            continue
        items = ext.body.block_items or []
        if len(items) < 2:
            continue
        new_items = rewrite_items(list(items))
        if new_items is not None:
            ext.body.block_items = new_items


def _transform_early_return_if_then_return(ast: c.FileAST) -> None:
    """Rewrite `if (c) return E1; ...; return E2;` → single-return.

    Pattern target: body con primo stmt `if (c) return E1;` (else-less),
    seguito da zero o più statement non-return, e ultimo stmt `return E2;`.

    Trasforma:
        int gcd(int a, int b) {
            if (b == 0) return a;
            return gcd(b, a % b);
        }
    in:
        int gcd(int a, int b) {
            int __mn_rv3 = 0;
            if (b == 0) __mn_rv3 = a;
            else { __mn_rv3 = gcd(b, a % b); }
            return __mn_rv3;
        }
    """
    rv_name = "__mn_rv3"

    def is_if_with_return_then(s: c.Node) -> bool:
        if not isinstance(s, c.If):
            return False
        if s.iffalse is not None:
            return False
        t = s.iftrue
        if isinstance(t, c.Compound):
            items = t.block_items or []
            if len(items) == 1 and isinstance(items[0], c.Return) and items[0].expr is not None:
                return True
            return False
        if isinstance(t, c.Return) and t.expr is not None:
            return True
        return False

    def _extract_then_return_expr(s: c.If) -> c.Node:
        t = s.iftrue
        if isinstance(t, c.Compound):
            return (t.block_items or [])[0].expr
        return t.expr

    for ext in ast.ext or []:
        if not isinstance(ext, c.FuncDef):
            continue
        if ext.body is None or not isinstance(ext.body, c.Compound):
            continue
        items = ext.body.block_items or []
        if len(items) < 2:
            continue
        first = items[0]
        last = items[-1]
        if not is_if_with_return_then(first):
            continue
        if not (isinstance(last, c.Return) and last.expr is not None):
            continue
        # Verifica che gli statement intermedi non contengano return.
        mid = items[1:-1]
        has_inner_return = False
        for s in mid:
            for sub in _iter_c_nodes(s):
                if isinstance(sub, c.Return):
                    has_inner_return = True
                    break
            if has_inner_return:
                break
        if has_inner_return:
            continue
        # Costruisci la nuova struttura.
        early_expr = _extract_then_return_expr(first)
        rv_decl = c.Decl(
            name=rv_name,
            quals=[], align=[], storage=[], funcspec=[],
            type=c.TypeDecl(
                declname=rv_name, quals=[], align=None,
                type=c.IdentifierType(names=["int"]),
            ),
            init=c.Constant(type="int", value="0"),
            bitsize=None,
        )
        early_assign = c.Assignment(
            op="=", lvalue=c.ID(name=rv_name), rvalue=early_expr,
        )
        late_assign = c.Assignment(
            op="=", lvalue=c.ID(name=rv_name), rvalue=last.expr,
        )
        else_block_items: list[c.Node] = list(mid) + [late_assign]
        new_if = c.If(
            cond=first.cond,
            iftrue=early_assign,
            iffalse=c.Compound(block_items=else_block_items),
        )
        ext.body.block_items = [
            rv_decl,
            new_if,
            c.Return(expr=c.ID(name=rv_name)),
        ]


def _transform_if_chain_returns(ast: c.FileAST) -> None:
    """Rewrite `return V;` in if/else-if/else chain body.

    Pattern target: body `{ if (c1) return E1; else if (c2) return E2; ... else return En; }`
    Riscrive in: `int __mn_rv = 0; if (c1) __mn_rv = E1; else if (c2) __mn_rv = E2; ... else __mn_rv = En; return __mn_rv;`
    """
    rv_name = "__mn_rv2"

    def is_return_chain(node: c.Node) -> bool:
        if isinstance(node, c.Return) and node.expr is not None:
            return True
        if isinstance(node, c.If):
            t = node.iftrue
            f = node.iffalse
            if not _stmt_is_return_or_chain(t):
                return False
            if f is None:
                return False
            if not _stmt_is_return_or_chain(f):
                return False
            return True
        return False

    def _stmt_is_return_or_chain(node: c.Node | None) -> bool:
        if node is None:
            return False
        if isinstance(node, c.Compound):
            items = node.block_items or []
            if len(items) != 1:
                return False
            return is_return_chain(items[0])
        return is_return_chain(node)

    def rewrite_chain(node: c.Node) -> c.Node | None:
        if isinstance(node, c.Return) and node.expr is not None:
            return c.Assignment(op="=", lvalue=c.ID(name=rv_name), rvalue=node.expr)
        if isinstance(node, c.If):
            t = _wrap_or_extract(node.iftrue)
            f = _wrap_or_extract(node.iffalse)
            new_t = rewrite_chain(t)
            new_f = rewrite_chain(f)
            return c.If(cond=node.cond, iftrue=new_t, iffalse=new_f)
        return None

    def _wrap_or_extract(node: c.Node | None) -> c.Node | None:
        if node is None:
            return None
        if isinstance(node, c.Compound):
            items = node.block_items or []
            if len(items) == 1:
                return items[0]
        return node

    for ext in ast.ext or []:
        if not isinstance(ext, c.FuncDef):
            continue
        if ext.body is None or not isinstance(ext.body, c.Compound):
            continue
        items = ext.body.block_items or []
        if len(items) != 1:
            continue
        head = items[0]
        if not isinstance(head, c.If):
            continue
        if not is_return_chain(head):
            continue
        rv_decl = c.Decl(
            name=rv_name,
            quals=[], align=[], storage=[], funcspec=[],
            type=c.TypeDecl(
                declname=rv_name, quals=[], align=None,
                type=c.IdentifierType(names=["int"]),
            ),
            init=c.Constant(type="int", value="0"),
            bitsize=None,
        )
        new_if = rewrite_chain(head)
        if new_if is None:
            continue
        ext.body.block_items = [
            rv_decl,
            new_if,
            c.Return(expr=c.ID(name=rv_name)),
        ]


def _transform_switch_returns(ast: c.FileAST) -> None:
    """Rewrite `return V;` dentro `case`/`default` di un body switch-only.

    Pattern target — funzioni il cui body è solo `switch(X) { case A: return V1; ... }`:
    le `return` non-finali di Mnemo sono no-op (VM reversibile no early-exit).

    Trasforma:
        int f(int x) {
            switch (x) {
                case 0: return 100;
                case 1: return 200;
                default: return 999;
            }
        }
    in:
        int f(int x) {
            int __mn_rv = 0;
            switch (x) {
                case 0: __mn_rv = 100; break;
                case 1: __mn_rv = 200; break;
                default: __mn_rv = 999; break;
            }
            return __mn_rv;
        }
    """
    rv_name = "__mn_rv"
    for ext in ast.ext or []:
        if not isinstance(ext, c.FuncDef):
            continue
        if ext.body is None or not isinstance(ext.body, c.Compound):
            continue
        items = ext.body.block_items or []
        if len(items) != 1 or not isinstance(items[0], c.Switch):
            continue
        sw = items[0]
        if not isinstance(sw.stmt, c.Compound):
            continue
        case_items = sw.stmt.block_items or []
        # Verifica che ogni `case X:` finisca con `return E;` (no fall-through).
        # Pattern accettato: il payload di case è esattamente `[return E]` o `[stmt; return E]`.
        all_cases_have_return = True
        for it in case_items:
            if not isinstance(it, (c.Case, c.Default)):
                all_cases_have_return = False
                break
            payload = it.stmts or []
            if not payload:
                all_cases_have_return = False
                break
            last = payload[-1]
            if not isinstance(last, c.Return) or last.expr is None:
                all_cases_have_return = False
                break
        if not all_cases_have_return:
            continue
        # Trasforma in-place.
        new_block_items: list[c.Node] = []
        # local int __mn_rv = 0;
        rv_decl = c.Decl(
            name=rv_name,
            quals=[],
            align=[],
            storage=[],
            funcspec=[],
            type=c.TypeDecl(
                declname=rv_name, quals=[], align=None,
                type=c.IdentifierType(names=["int"]),
            ),
            init=c.Constant(type="int", value="0"),
            bitsize=None,
        )
        new_block_items.append(rv_decl)
        # Rewrite ogni case: ultimo `return E` → `__mn_rv = E; break;`.
        for it in case_items:
            payload = it.stmts or []
            ret_stmt = payload[-1]
            assert isinstance(ret_stmt, c.Return)
            assign = c.Assignment(
                op="=",
                lvalue=c.ID(name=rv_name),
                rvalue=ret_stmt.expr,
            )
            brk = c.Break()
            it.stmts = list(payload[:-1]) + [assign, brk]
        new_block_items.append(sw)
        # return __mn_rv;
        new_block_items.append(c.Return(expr=c.ID(name=rv_name)))
        ext.body.block_items = new_block_items


def _iter_c_nodes(node: c.Node | None) -> list[c.Node]:
    """Attraversamento depth-first (pycparser `children()`)."""
    if node is None:
        return []
    out: list[c.Node] = [node]
    for _name, child in node.children():
        if child is None:
            continue
        if isinstance(child, list):
            for ch in child:
                out.extend(_iter_c_nodes(ch))
        else:
            out.extend(_iter_c_nodes(child))
    return out


def _ptr_to_struct_tag(ptr_decl: c.PtrDecl) -> str | None:
    """Estrae il tag struct da `PtrDecl(TypeDecl(IdentifierType([tag])))`.

    Restituisce None se non è un puntatore a typedef/struct semplice.
    """
    inner = ptr_decl.type
    if not isinstance(inner, c.TypeDecl):
        return None
    t = inner.type
    if isinstance(t, c.Struct) and t.name:
        return t.name
    if isinstance(t, c.IdentifierType) and len(t.names) == 1:
        return t.names[0]
    return None


def _collect_file_scope_struct_arrays(
    ast: c.FileAST,
) -> dict[str, c.StructRef | c.ID]:
    """Mappa struct_tag → AST node che identifica l'array di struct file-scope.

    Pattern supportati:
    - `T arr[N];` (top-level array of struct/typedef) → node = c.ID(arr).
    - `BoxT B; B contiene `T arr[N]` campo → node = c.StructRef(B.arr).

    Solo una entry per tag (ambiguità: prima trovata vince — gli usi
    devono essere a singola istanza).
    """
    # Tag → struct-definition (decls) map (typedef + file-scope struct decls).
    tag_struct: dict[str, c.Struct] = {}
    for ext in ast.ext or []:
        # File-scope hoisted struct decl: `c.Decl(name=None, type=Struct(name=tag, decls=...))`.
        if isinstance(ext, c.Decl) and isinstance(ext.type, c.Struct) and ext.type.decls:
            if ext.type.name:
                tag_struct[ext.type.name] = ext.type
        if isinstance(ext, c.Typedef) and isinstance(ext.type, c.TypeDecl):
            inner = ext.type.type
            if isinstance(inner, c.Struct) and inner.name:
                if inner.decls:
                    tag_struct[inner.name] = inner
                    tag_struct[ext.name] = inner
                elif inner.name in tag_struct:
                    # Riferimento a tag-only: typedef → struct file-scope già hoistata.
                    tag_struct[ext.name] = tag_struct[inner.name]
            elif isinstance(inner, c.IdentifierType) and len(inner.names) == 1:
                # `typedef U V;` — risolveremo lazy.
                pass

    # Seconda passata: typedef→typedef alias (chain) — risolvi typedef A che
    # punta a typedef B (entrambi su struct).
    for ext in ast.ext or []:
        if isinstance(ext, c.Typedef) and isinstance(ext.type, c.TypeDecl):
            inner = ext.type.type
            if (
                isinstance(inner, c.Struct) and inner.name
                and inner.name in tag_struct
                and ext.name not in tag_struct
            ):
                tag_struct[ext.name] = tag_struct[inner.name]

    def _resolve_struct(node: c.Node) -> c.Struct | None:
        if isinstance(node, c.Struct) and node.decls:
            return node
        if isinstance(node, c.Struct) and node.name in tag_struct:
            return tag_struct[node.name]
        if isinstance(node, c.IdentifierType) and len(node.names) == 1:
            return tag_struct.get(node.names[0])
        return None

    def _array_of_struct_tag(at: c.ArrayDecl) -> str | None:
        elem = at.type
        while isinstance(elem, c.ArrayDecl):
            elem = elem.type
        if isinstance(elem, c.TypeDecl):
            t = elem.type
            if isinstance(t, c.IdentifierType) and len(t.names) == 1:
                return t.names[-1]
            if isinstance(t, c.Struct) and t.name:
                return t.name
        return None

    out: dict[str, c.StructRef | c.ID] = {}
    for ext in ast.ext or []:
        if not isinstance(ext, c.Decl) or not ext.name:
            continue
        # Variabile globale di tipo struct → cerca campi array-of-struct.
        if isinstance(ext.type, c.TypeDecl):
            s = _resolve_struct(ext.type.type)
            if s is not None and s.decls:
                for fd in s.decls:
                    if not isinstance(fd, c.Decl) or not fd.name:
                        continue
                    if isinstance(fd.type, c.ArrayDecl):
                        tag = _array_of_struct_tag(fd.type)
                        if tag and tag not in out:
                            out[tag] = c.StructRef(
                                name=c.ID(name=ext.name),
                                type=".",
                                field=c.ID(name=str(fd.name)),
                            )
        # Array of struct top-level: `T arr[N];`.
        if isinstance(ext.type, c.ArrayDecl):
            tag = _array_of_struct_tag(ext.type)
            if tag and tag not in out:
                out[tag] = c.ID(name=ext.name)
    return out


def _transform_struct_array_pointer_alias(ast: c.FileAST) -> None:
    """Riscrittura AST: `T* p = &BASE.arr[idx]` con `BASE.arr` array di struct
    → trattare `p` come int holding idx; sostituire `p->f` con `BASE.arr[p].f`.

    Cross-fn: se `void f(T* p)` ha `T` con file-scope struct-array unico
    `BASE.arr` di tipo `T`, `p` è promosso ad alias di `BASE.arr` nel body
    della funzione. Caller può passare un alias come argomento.

    Limiti correnti:
    - File scope: deve esistere una sola struct-array per ciascun tag T usato
      come `T*` parametro (altrimenti ambiguo).
    - Alias non resettato fino a fine funzione (nessun reset interno).
    - Solo accessi `p->f` (no `*p`, no `p[k]`).
    """
    file_arrays = _collect_file_scope_struct_arrays(ast)
    # Per-funzione alias: {fn_name: {var_name: arr_ref}}.
    fn_aliases: dict[str, dict[str, c.Node]] = {}
    # Per-funzione: nome param → True se è un alias struct-array (per validazione).
    fn_param_aliases: dict[str, set[str]] = {}

    # Pass 1: scan params + local Decls in ogni funzione.
    for ext in ast.ext or []:
        if not isinstance(ext, c.FuncDef):
            continue
        fname = ext.decl.name
        aliases: dict[str, c.Node] = {}
        param_aliases: set[str] = set()
        # Param scan: `T* p` con T tag in file_arrays.
        fdtype = ext.decl.type
        if isinstance(fdtype, c.FuncDecl) and fdtype.args is not None:
            for prm in fdtype.args.params or []:
                if not isinstance(prm, c.Decl) or not prm.name:
                    continue
                if isinstance(prm.type, c.PtrDecl):
                    tag = _ptr_to_struct_tag(prm.type)
                    if tag and tag in file_arrays:
                        aliases[str(prm.name)] = file_arrays[tag]
                        param_aliases.add(str(prm.name))
        # Body scan: `T* p = &BASE.arr[idx];` con T = struct tag conosciuto.
        if ext.body is not None:
            for n in _iter_c_nodes(ext.body):
                if not isinstance(n, c.Decl) or not n.name:
                    continue
                if not isinstance(n.type, c.PtrDecl):
                    continue
                # Type filter: solo `struct_tag*` su tag con struct-array file-scope.
                ptag = _ptr_to_struct_tag(n.type)
                if ptag is None or ptag not in file_arrays:
                    continue
                init = n.init
                if not isinstance(init, c.UnaryOp) or init.op != "&":
                    continue
                inner = init.expr
                if not isinstance(inner, c.ArrayRef):
                    continue
                if not isinstance(inner.name, (c.StructRef, c.ID)):
                    continue
                aliases[str(n.name)] = inner.name
        fn_aliases[fname] = aliases
        fn_param_aliases[fname] = param_aliases

    # Pass 2: validate FuncCall args — se arg è alias, callee param matching
    # deve anch'esso essere alias.
    for ext in ast.ext or []:
        if not isinstance(ext, c.FuncDef):
            continue
        fname = ext.decl.name
        aliases = fn_aliases.get(fname, {})
        if not aliases or ext.body is None:
            continue
        for n in _iter_c_nodes(ext.body):
            if isinstance(n, c.FuncCall) and n.args is not None:
                callee_name = getattr(n.name, "name", None)
                callee_aliases = fn_param_aliases.get(callee_name, set())
                # Recupera param names del callee (ordinati).
                callee_def = None
                for e2 in ast.ext or []:
                    if isinstance(e2, c.FuncDef) and e2.decl.name == callee_name:
                        callee_def = e2
                        break
                callee_param_names: list[str] = []
                if callee_def is not None:
                    fdt = callee_def.decl.type
                    if isinstance(fdt, c.FuncDecl) and fdt.args is not None:
                        for prm in fdt.args.params or []:
                            if isinstance(prm, c.Decl) and prm.name:
                                callee_param_names.append(str(prm.name))
                for i, arg in enumerate(n.args.exprs or []):
                    if isinstance(arg, c.ID) and arg.name in aliases:
                        # Callee param matching deve essere alias.
                        if (
                            i < len(callee_param_names)
                            and callee_param_names[i] in callee_aliases
                        ):
                            continue
                        raise MnemoCompileError(
                            f"`{arg.name}` (alias struct-array) passato a "
                            f"`{callee_name}` ma il parametro corrispondente "
                            f"non è riconosciuto come alias struct-array. "
                            f"Verifica che il param sia `T*` con T struct-array "
                            f"file-scope unico."
                        )

    # Pass 3: rewrite ogni funzione.
    for ext in ast.ext or []:
        if not isinstance(ext, c.FuncDef):
            continue
        fname = ext.decl.name
        aliases = fn_aliases.get(fname, {})
        if not aliases:
            continue
        param_aliases = fn_param_aliases.get(fname, set())

        # Rewrite params: `T* p` → `int p`.
        fdtype = ext.decl.type
        if isinstance(fdtype, c.FuncDecl) and fdtype.args is not None:
            for prm in fdtype.args.params or []:
                if (
                    isinstance(prm, c.Decl) and prm.name
                    and prm.name in param_aliases
                    and isinstance(prm.type, c.PtrDecl)
                ):
                    inner_td = prm.type.type
                    if isinstance(inner_td, c.TypeDecl):
                        prm.type = c.TypeDecl(
                            declname=inner_td.declname,
                            quals=[],
                            align=None,
                            type=c.IdentifierType(names=["int"]),
                        )

        def _rewrite(node: c.Node, aliases=aliases) -> c.Node:
            for child_name, ch in list(node.children()):
                if ch is None:
                    continue
                if isinstance(ch, list):
                    new_list = [_rewrite(x) if x is not None else None for x in ch]
                    base_name = child_name.split("[")[0] if "[" in child_name else child_name
                    setattr(node, base_name, new_list)
                else:
                    new_ch = _rewrite(ch)
                    if new_ch is not ch:
                        setattr(node, child_name, new_ch)
            # Decl: `T* p = &BASE.arr[idx];` → `int p = idx;`.
            if isinstance(node, c.Decl) and node.name in aliases:
                if isinstance(node.type, c.PtrDecl):
                    inner_td = node.type.type
                    if isinstance(inner_td, c.TypeDecl):
                        node.type = c.TypeDecl(
                            declname=inner_td.declname,
                            quals=[],
                            align=None,
                            type=c.IdentifierType(names=["int"]),
                        )
                init = node.init
                if (
                    isinstance(init, c.UnaryOp) and init.op == "&"
                    and isinstance(init.expr, c.ArrayRef)
                ):
                    node.init = init.expr.subscript
                return node
            # Assignment `p = &BASE.arr[idx];` → `p = idx;`.
            if (
                isinstance(node, c.Assignment) and node.op == "="
                and isinstance(node.lvalue, c.ID) and node.lvalue.name in aliases
            ):
                rv = node.rvalue
                if (
                    isinstance(rv, c.UnaryOp) and rv.op == "&"
                    and isinstance(rv.expr, c.ArrayRef)
                ):
                    node.rvalue = rv.expr.subscript
                return node
            # `p->field` → `BASE.arr[p].field`.
            if (
                isinstance(node, c.StructRef) and node.type == "->"
                and isinstance(node.name, c.ID) and node.name.name in aliases
            ):
                base = aliases[node.name.name]
                node.type = "."
                node.name = c.ArrayRef(
                    name=base,
                    subscript=c.ID(name=node.name.name),
                )
            return node
        if ext.body is not None:
            _rewrite(ext.body)


def _collect_u32_typedefs(ast: c.FileAST) -> set[str]:
    """Set di typedef name che risolvono a `unsigned int` / `unsigned`.

    Ricorsivo su typedef-of-typedef. `uint32_t`, `u32`, ecc.
    """
    direct: dict[str, str | None] = {}  # name → underlying typedef name (or None se base)
    base_unsigned: set[str] = set()
    for ext in ast.ext or []:
        if not isinstance(ext, c.Typedef):
            continue
        t = ext.type
        if not isinstance(t, c.TypeDecl):
            continue
        inner = t.type
        if isinstance(inner, c.IdentifierType):
            names = tuple(inner.names)
            if names in (("unsigned", "int"), ("unsigned",)):
                base_unsigned.add(ext.name)
            elif len(names) == 1:
                direct[ext.name] = names[0]
    # Risoluzione transitiva.
    out: set[str] = set(base_unsigned)
    changed = True
    while changed:
        changed = False
        for n, ref in direct.items():
            if n in out:
                continue
            if ref in out:
                out.add(n)
                changed = True
    return out


def _is_u32_type_node(t: c.Node | None, u32_typedefs: set[str]) -> bool:
    """True se il nodo tipo (TypeDecl wrapping IdentifierType) è u32."""
    if isinstance(t, c.TypeDecl):
        t = t.type
    if isinstance(t, c.IdentifierType):
        names = tuple(t.names)
        if names in (("unsigned", "int"), ("unsigned",)):
            return True
        if len(names) == 1 and names[0] in u32_typedefs:
            return True
    return False


def _transform_u32_modular_masks(ast: c.FileAST) -> None:
    """Inserisce `__mn_mask_u32(&x)` dopo ogni assignment ad una variabile u32.

    Mnemo cell è int64; ops aritmetiche/shift/bitwise C su u32 dovrebbero
    troncare a 32 bit. Mask via helper lib (`mnsplit32`-based, O(1) VM op),
    NON via `&=` (che usa `__mn_and_into` 31-iter — overhead massivo).

    Limiti correnti:
    - Solo lvalue = c.ID di variabile dichiarata localmente o param u32 nel
      contesto. Struct field u32, array element u32, deref puntatori u32:
      non gestiti.
    - Compound ops (`+=`, `^=`, `*=`, etc.): masked dopo l'op.
    - `++`/`--`: masked dopo.
    - L'rvalue di un assignment non viene maskato (i ops intermedi in int64
      sono safe; solo lo store finale serve mask).
    """
    u32_typedefs = _collect_u32_typedefs(ast)

    def _decl_is_u32(d: c.Decl) -> bool:
        return _is_u32_type_node(d.type, u32_typedefs)

    def _collect_u32_vars_in_func(fd: c.FuncDef) -> set[str]:
        """Variabili u32 visibili (params + locals di tutti scope)."""
        names: set[str] = set()
        fdt = fd.decl.type
        if isinstance(fdt, c.FuncDecl) and fdt.args is not None:
            for prm in fdt.args.params or []:
                if isinstance(prm, c.Decl) and prm.name and _decl_is_u32(prm):
                    names.add(str(prm.name))
        if fd.body is None:
            return names
        for n in _iter_c_nodes(fd.body):
            if isinstance(n, c.Decl) and n.name and _decl_is_u32(n):
                names.add(str(n.name))
        return names

    def _mask_stmt(var_name: str, coord: object) -> c.Node:
        # Call `__mn_mask_u32(x)` — lib helper O(1) via mnsplit32.
        # Param `int x` Kairos: cell shared con caller (by-reference).
        return c.FuncCall(
            name=c.ID(name="__mn_mask_u32", coord=coord),
            args=c.ExprList(exprs=[
                c.ID(name=var_name, coord=coord),
            ], coord=coord),
            coord=coord,
        )

    def _needs_mask(rhs: c.Node) -> bool:
        # Skip se rhs è costante che già fits in u32.
        if isinstance(rhs, c.Constant):
            try:
                v = int(rhs.value, 0)
                if 0 <= v <= 0xFFFFFFFF:
                    return False
            except (ValueError, TypeError):
                pass
        return True

    def _wrap_compound(items: list[c.Node], u32_vars: set[str]) -> list[c.Node]:
        out: list[c.Node] = []
        for s in items:
            new_s = _rewrite(s, u32_vars)
            out.append(new_s)
            # Dopo lo statement, inserisci mask se è un assignment a u32 ID.
            extra = _trailing_masks(new_s, u32_vars)
            out.extend(extra)
        return out

    def _trailing_masks(s: c.Node, u32_vars: set[str]) -> list[c.Node]:
        if isinstance(s, c.Assignment) and isinstance(s.lvalue, c.ID):
            if s.lvalue.name in u32_vars:
                op = s.op
                # Compound op (`+=`, `*=`, `<<=`, `-=`) può eccedere 32 bit
                # anche se rvalue fits → maschera sempre. Solo `=` puro con
                # rvalue costante fits-u32 può saltare il mask.
                # `^=`, `&=`, `|=`, `>>=` non crescono ma maskiamo comunque
                # per coerenza/idempotenza.
                if op == "=":
                    if _needs_mask(s.rvalue):
                        return [_mask_stmt(s.lvalue.name, s.coord)]
                else:
                    return [_mask_stmt(s.lvalue.name, s.coord)]
        if isinstance(s, c.UnaryOp) and s.op in ("p++", "p--", "++", "--"):
            if isinstance(s.expr, c.ID) and s.expr.name in u32_vars:
                return [_mask_stmt(s.expr.name, s.coord)]
        return []

    def _rewrite(s: c.Node, u32_vars: set[str]) -> c.Node:
        if isinstance(s, c.Compound):
            new_items = _wrap_compound(list(s.block_items or []), u32_vars)
            return c.Compound(block_items=new_items, coord=s.coord)
        if isinstance(s, c.If):
            return c.If(
                cond=s.cond,
                iftrue=_rewrite(s.iftrue, u32_vars) if s.iftrue is not None else None,
                iffalse=_rewrite(s.iffalse, u32_vars) if s.iffalse is not None else None,
                coord=s.coord,
            )
        if isinstance(s, c.While):
            return c.While(cond=s.cond, stmt=_rewrite(s.stmt, u32_vars), coord=s.coord)
        if isinstance(s, c.DoWhile):
            return c.DoWhile(cond=s.cond, stmt=_rewrite(s.stmt, u32_vars), coord=s.coord)
        if isinstance(s, c.For):
            return c.For(
                init=s.init, cond=s.cond, next=s.next,
                stmt=_rewrite(s.stmt, u32_vars), coord=s.coord,
            )
        if isinstance(s, c.Switch):
            return c.Switch(cond=s.cond, stmt=_rewrite(s.stmt, u32_vars), coord=s.coord)
        if isinstance(s, c.Case):
            return c.Case(
                expr=s.expr,
                stmts=_wrap_compound(list(s.stmts or []), u32_vars),
                coord=s.coord,
            )
        if isinstance(s, c.Default):
            return c.Default(
                stmts=_wrap_compound(list(s.stmts or []), u32_vars),
                coord=s.coord,
            )
        return s

    for ext in ast.ext or []:
        if not isinstance(ext, c.FuncDef):
            continue
        u32_vars = _collect_u32_vars_in_func(ext)
        if not u32_vars or ext.body is None:
            continue
        items = list(ext.body.block_items or [])
        ext.body.block_items = _wrap_compound(items, u32_vars)


def _ast_needs_two_mem_partitions(ast: c.FileAST) -> bool:
    """
    `par` a due rami con call che condividono le stesse celle `__mn_mem*`
    → race in Kairos. Raddoppiamo lo spazio (`2 * S` celle) e passiamo
    argomenti disgiunti per branch (vedi c_lower, `mnemo_pthread_parallel*`).
    """
    for n in _iter_c_nodes(ast):
        if isinstance(n, c.FuncCall) and isinstance(n.name, c.ID):
            if n.name.name in PTHREAD_ABI_TWO_REGION_PAR:
                return True
    return False


def _merge_lib_lists(a: list[str], b: list[str]) -> list[str]:
    """Concatena senza duplicati, preservando l’ordine (prima `a`, poi nuovi da `b`)."""
    seen: set[str] = set()
    out: list[str] = []
    for x in a + b:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out


def _instr_list_uses_ptr_pool(instrs: list[Instr]) -> bool:
    for ins in instrs:
        if isinstance(ins, ICall) and ins.proc.startswith("__mn_pool_"):
            return True
        if isinstance(ins, IPar):
            for br in ins.branches:
                if _instr_list_uses_ptr_pool(br):
                    return True
        if isinstance(ins, IIfKairos):
            if _instr_list_uses_ptr_pool(ins.then_instrs):
                return True
            if ins.else_instrs and _instr_list_uses_ptr_pool(ins.else_instrs):
                return True
        if isinstance(ins, IFromUntilKairos):
            if _instr_list_uses_ptr_pool(ins.body_instrs):
                return True
        if isinstance(ins, ILocalBlock):
            if _instr_list_uses_ptr_pool(ins.body_instrs):
                return True
    return False


def _program_uses_ptr_pool(prog: Program) -> bool:
    """True se l'IR contiene chiamate ai runtime pool (serve il preambolo `emit_ptr_pool_kairos`)."""
    for fn in prog.functions:
        for blk in fn.blocks:
            if _instr_list_uses_ptr_pool(blk.instrs):
                return True
    return False


def _instr_list_uses_floor_snap_instr(instrs: list[Instr]) -> bool:
    stack: list[list[Instr]] = [instrs]
    while stack:
        cur = stack.pop()
        for ins in cur:
            if isinstance(ins, ICall) and ins.proc == "__mn_hist_floor_snap":
                return True
            if isinstance(ins, IIfKairos):
                stack.append(ins.then_instrs or [])
                if ins.else_instrs:
                    stack.append(ins.else_instrs)
            elif isinstance(ins, IFromUntilKairos):
                stack.append(ins.body_instrs or [])
            elif isinstance(ins, ILocalBlock):
                stack.append(ins.body_instrs or [])
            elif isinstance(ins, IPar):
                for br in ins.branches or []:
                    stack.append(br)
    return False


def _program_uses_hist_floor_snap(prog: Program) -> bool:
    """IR con `call __mn_hist_floor_snap` (--opt-uncall-user-calls) → prelude `mn_hist_floor_snap.kairos`."""
    return any(
        _instr_list_uses_floor_snap_instr(b.instrs)
        for fn in prog.functions
        for b in fn.blocks
    )


# Prima riga del .kairos: il frontend Kairos la rimuove e disattiva il check
# «race su int nel PAR» (serve per variabili file-scope condivise + mutex Mnemo).
KAIROS_ALLOW_PAR_SHARED_INT_PRAGMA = "// KAIROS_ALLOW_PAR_SHARED_INT\n"


def _wrap_main_in_invertibility_check(prog: Program) -> None:
    """Sposta corpo `main` in nuova proc `__main__(stack hist, stack scratch)` e
    sostituisce `main` con un wrapper che fa `call __main__ ; uncall __main__`.

    Verifica al 100% che il corpo C sia reversibile: se l'inverso fallisce
    (delocal mismatch, pop empty, ecc.) la VM lo segnala subito.
    """
    main_idx = next(
        (i for i, fn in enumerate(prog.functions) if fn.name == "main"), -1
    )
    if main_idx < 0:
        return
    old_main = prog.functions[main_idx]
    # hist+scratch diventano parametri di __main__: rimuovili dai `local stack` del main.
    inner_locals = [
        (t, n)
        for (t, n) in old_main.locals
        if not (t == "stack" and n in ("__mn_hist", "__mn_scratch"))
    ]
    inner = Function(
        name="__main__",
        params=[("stack", "__mn_hist"), ("stack", "__mn_scratch")],
        locals=inner_locals,
        blocks=list(old_main.blocks),
    )
    wrapper_body = [
        ICall("__main__", ["__mn_hist", "__mn_scratch"]),
        IUncall("__main__", ["__mn_hist", "__mn_scratch"]),
    ]
    wrapper = Function(
        name="main",
        params=[],
        locals=[("stack", "__mn_hist"), ("stack", "__mn_scratch")],
        blocks=[Block(bid="entry", instrs=wrapper_body)],
    )
    prog.functions[main_idx] = inner
    prog.functions.append(wrapper)


def compile_c_to_kairos(
    path: str,
    *,
    main_argc: int | None = None,
    ptr_pool_size: int = 4,
    opt_uncall_user_calls: bool = False,
    check_invertibility: bool = False,
    arr_max: int | None = None,
) -> str:
    if arr_max is not None:
        if arr_max < 1 or arr_max > 65536:
            raise MnemoCompileError(
                f"arr_max fuori intervallo (1..65536): {arr_max}"
            )
        import mnemo.c_lower as _cl
        _cl.ARR_MAX = arr_max
    try:
        with open(path, encoding="utf-8") as f:
            src = f.read()
    except OSError as e:
        raise MnemoCompileError(f"file non trovato o non leggibile: {path}") from e
    ast = parse_c(path)
    # K&R: convert `int foo(a, b) int a; int b; { … }` → ANSI param form.
    _convert_kr_to_ansi(ast)
    # Anonymous struct/union: `struct { ... } p;` → assegna tag sintetico.
    _name_anonymous_structs_unions(ast)
    # CompoundLiteral hoist: `(T[]){...}` → Decl sintetico nel body della funzione
    # contenente. Deve girare PRIMA di `compute_program_mem_layout` così le celle
    # vengono allocate per gli array sintetici.
    _hoist_compound_literals_in_ast(ast)
    # `static int n = …;` → file-scope Decl rinominato. Persiste tra chiamate.
    _hoist_static_locals(ast)
    # `f("lit")` → `char *__mn_anon_str_k = "lit"; f(__mn_anon_str_k)` (skip
    # printf-family). Materializza in pool prima del layout per allocare celle.
    _hoist_string_literal_call_args_in_ast(ast)
    # `return E;` dentro for/while → return-flag globale, body skipped via
    # `if (!flag)`. Loop esegue tutte le iter ma il body è no-op dopo flag.
    _transform_return_in_loop(ast)
    # `int f(...) { switch(...) { case A: return V; ... } }` → single-return.
    _transform_switch_returns(ast)
    # `int f(...) { if (c1) return E1; else if (c2) return E2; ... }` → single-return.
    _transform_if_chain_returns(ast)
    # `int f(...) { if (c) return E1; ...; return E2; }` → single-return.
    _transform_early_return_if_then_return(ast)
    # Generalizzazione: ammette qualsiasi numero di stmt prima del primo
    # `if(c) return E`. Cascade trattata ricorsivamente sul ramo else.
    _transform_general_early_returns(ast)
    # `if (E) S` con S che muta var di E → hoist E in fresh int (fi stabile).
    _transform_hoist_unsafe_if_conds(ast)
    # `T* p = &BASE.arr[i]; ... p->f ...` → alias inline a `BASE.arr[p].f` (int p).
    _transform_struct_array_pointer_alias(ast)
    # u32 vars: inserisce `__mn_mask_u32(&x)` dopo ogni assignment per emulare
    # semantica modular C. Helper lib basato su mnsplit32 (O(1) VM op).
    _transform_u32_modular_masks(ast)
    proc_index = lib_procedure_index()
    lib_names = _merge_lib_lists(
        infer_auto_lib_files(ast),
        infer_lib_files_from_calls(ast, proc_index),
    )
    argc_use = parse_mnemo_main_argc(src) if main_argc is None else main_argc
    if argc_use < 0:
        raise MnemoCompileError("main_argc deve essere >= 0")
    layout = compute_program_mem_layout(ast, ptr_pool_size)
    mem_units = 2 if _ast_needs_two_mem_partitions(ast) else 1
    physical_mem_cells = layout.total_cells * mem_units
    if layout.total_cells > PTR_POOL_MAX:
        raise MnemoCompileError(
            f"celle memoria (layout) {layout.total_cells} superano il limite pool "
            f"{PTR_POOL_MAX} (prova a ridurre --ptr-pool-size o le variabili C)"
        )
    if (
        mem_units == 2
        and layout.parallel_file_shared_slots
        and not parse_mnemo_skip_par_shared_mutex_check(src)
    ):
        check_par_shared_mutex_discipline(ast, layout)
    prog = lower_file_to_program(
        ast,
        main_argc=argc_use,
        ptr_pool_size=ptr_pool_size,
        layout=layout,
        physical_mem_cells=physical_mem_cells,
        opt_uncall_user_calls=opt_uncall_user_calls,
    )
    prog = maybe_inline_user_functions(
        ast, prog, total_mem_cells=layout.total_cells
    )
    if check_invertibility:
        _wrap_main_in_invertibility_check(prog)
    if _program_uses_ptr_pool(prog):
        lib_names = _merge_lib_lists(lib_names, ["ptr_pool.kairos"])
    if _program_uses_hist_floor_snap(prog):
        lib_names = _merge_lib_lists(["mn_hist_floor_snap.kairos"], lib_names)
    try:
        prelude = load_prelude_kairos(
            lib_names,
            ptr_pool_size=ptr_pool_size,
            # Pool: una finestra di S celle per call; il PAR usa due finestre disgiunte in main.
            total_mem_cells=layout.total_cells,
        )
    except FileNotFoundError as e:
        raise MnemoCompileError(str(e)) from e
    body = emit_program(prog)
    out = (prelude + body) if prelude else body
    if (
        mem_units == 2
        and layout.parallel_file_shared_slots
    ):
        out = KAIROS_ALLOW_PAR_SHARED_INT_PRAGMA + out
    return out


def write_kairos_next_to_c(c_path: str, content: str) -> str:
    """Scrive `stem.kairos` nella stessa directory di `c_path`. Ritorna il path scritto."""
    from pathlib import Path

    p = Path(c_path).resolve()
    out = p.with_suffix(".kairos")
    out.write_text(content, encoding="utf-8")
    return str(out)
