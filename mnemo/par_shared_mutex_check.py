"""
Controllo statico: con PAR a due regioni e variabili file-scope condivise (stesso __mn_mem),
due worker che accedono agli stessi slot senza mutex a livello file → errore di compilazione.

Condizione allineata a // KAIROS_ALLOW_PAR_SHARED_INT in compile.py.
"""

from __future__ import annotations

import pycparser.c_ast as c

from mnemo.c_lower import _get_funcdef, collect_file_scope_mutex_names
from mnemo.errors import MnemoCompileError
from mnemo.layout_collect import ProgramMemLayout


def file_scope_shared_logical_names(layout: ProgramMemLayout) -> frozenset[str]:
    """Nomi logici (``(\"__file__\", name)``) i cui indici sono in ``parallel_file_shared_slots``."""
    out: set[str] = set()
    for (fn, logical), idx in layout.slot_of.items():
        if fn != "__file__":
            continue
        if idx not in layout.parallel_file_shared_slots:
            continue
        out.add(logical)
    return frozenset(out)


def iter_par_worker_pairs(ast: c.FileAST) -> list[tuple[str, str]]:
    """Coppie (worker ramo A, worker ramo B) per ogni call ABI PAR a due rami."""
    out: list[tuple[str, str]] = []
    stack: list[c.Node | None] = [ast]
    while stack:
        n = stack.pop()
        if n is None:
            continue
        if isinstance(n, c.FuncCall) and isinstance(n.name, c.ID):
            nm = n.name.name
            el = n.args
            exprs = list(el.exprs) if el is not None else []
            if nm == "mnemo_pthread_parallel2" and len(exprs) >= 2:
                a0, a1 = exprs[0], exprs[1]
                if isinstance(a0, c.ID) and isinstance(a1, c.ID):
                    out.append((a0.name, a1.name))
            elif nm == "mnemo_pthread_parallel_with" and len(exprs) >= 2:
                a0, a1 = exprs[0], exprs[1]
                if isinstance(a0, c.ID) and isinstance(a1, c.ID):
                    out.append((a0.name, a1.name))
            elif nm == "mnemo_pthread_parallel_with1" and len(exprs) >= 3:
                a0, a2 = exprs[0], exprs[2]
                if isinstance(a0, c.ID) and isinstance(a2, c.ID):
                    out.append((a0.name, a2.name))
        for _na, ch in n.children():
            if isinstance(ch, list):
                stack.extend(ch)
            elif ch is not None:
                stack.append(ch)
    return out


def _refs_shared_in_function(fdef: c.FuncDef, shared: frozenset[str]) -> frozenset[str]:
    """ID file-scope condivisi referenziati nel corpo (solo lookup sintattico, no alias)."""
    found: set[str] = set()
    stack: list[c.Node | None] = [fdef.body]
    while stack:
        n = stack.pop()
        if n is None:
            continue
        if isinstance(n, c.ID) and n.name in shared:
            found.add(n.name)
        for _na, ch in n.children():
            if isinstance(ch, list):
                stack.extend(ch)
            elif ch is not None:
                stack.append(ch)
    return frozenset(found)


def _pthread_mutex_ptr_name(arg: c.Node) -> str | None:
    if isinstance(arg, c.UnaryOp) and arg.op == "&" and isinstance(arg.expr, c.ID):
        return arg.expr.name
    return None


def _join_held(a: str | None, b: str | None) -> str | None:
    return a if a == b else None


def _check_expr_access(
    expr: c.Node | None,
    held: str | None,
    conflict: frozenset[str],
) -> None:
    if expr is None:
        return
    stack: list[c.Node | None] = [expr]
    while stack:
        n = stack.pop()
        if n is None:
            continue
        if isinstance(n, c.ID):
            if n.name in conflict and held is None:
                raise MnemoCompileError(
                    "accesso a variabile file-scope condivisa nel PAR senza "
                    "pthread_mutex_lock su un pthread_mutex_t a livello file "
                    f"(nome logico {n.name!r}); altrimenti la VM perde reversibilità "
                    "e determinismo. Proteggi la sezione critica con lo stesso mutex "
                    "globale in entrambi i worker."
                )
        for _na, ch in n.children():
            if isinstance(ch, list):
                stack.extend(ch)
            elif ch is not None:
                stack.append(ch)


def _func_call_new_hold(
    call: c.FuncCall,
    held: str | None,
    file_mutexes: frozenset[str],
    conflict: frozenset[str],
) -> str | None:
    """
    Verifica argomenti per accessi illegali; se è lock/unlock su mutex file-scope,
    ritorna il nuovo held. Altrimenti ritorna `held` invariato.
    """
    if not isinstance(call.name, c.ID):
        _check_expr_access(call, held, conflict)
        return held
    nm = call.name.name
    el = call.args
    exprs = list(el.exprs) if el is not None else []
    if nm == "pthread_mutex_lock" and len(exprs) == 1:
        m = _pthread_mutex_ptr_name(exprs[0])
        if m is not None and m in file_mutexes:
            for a in exprs:
                _check_expr_access(a, held, conflict)
            return m
    if nm == "pthread_mutex_unlock" and len(exprs) == 1:
        m = _pthread_mutex_ptr_name(exprs[0])
        if m is not None and m in file_mutexes:
            for a in exprs:
                _check_expr_access(a, held, conflict)
            return None if held == m else held
    for a in exprs:
        _check_expr_access(a, held, conflict)
    return held


def _walk_stmt(
    node: c.Node | None,
    held: str | None,
    file_mutexes: frozenset[str],
    conflict: frozenset[str],
) -> str | None:
    if node is None:
        return held
    if isinstance(node, c.EmptyStatement):
        return held
    if isinstance(node, c.Typedef):
        return held
    if isinstance(node, c.Decl):
        if node.init is not None:
            _check_expr_access(node.init, held, conflict)
        return held
    if isinstance(node, c.Compound):
        h = held
        for it in node.block_items or []:
            h = _walk_stmt(it, h, file_mutexes, conflict)
        return h
    if isinstance(node, c.Assignment):
        _check_expr_access(node.rvalue, held, conflict)
        _check_expr_access(node.lvalue, held, conflict)
        return held
    if isinstance(node, c.UnaryOp):
        _check_expr_access(node.expr, held, conflict)
        return held
    if isinstance(node, c.ExprList):
        h = held
        for e in node.exprs:
            if isinstance(e, c.FuncCall):
                h = _func_call_new_hold(e, h, file_mutexes, conflict)
            else:
                _check_expr_access(e, h, conflict)
        return h
    if isinstance(node, c.FuncCall):
        return _func_call_new_hold(node, held, file_mutexes, conflict)
    # pycparser mette `(void)x;` come Cast in lista Compound (non ExprStmt).
    if isinstance(node, c.Cast):
        _check_expr_access(node.expr, held, conflict)
        return held
    if isinstance(node, c.If):
        _check_expr_access(node.cond, held, conflict)
        ht = _walk_stmt(node.iftrue, held, file_mutexes, conflict)
        hf = _walk_stmt(node.iffalse, held, file_mutexes, conflict) if node.iffalse else held
        return _join_held(ht, hf)
    if isinstance(node, (c.While, c.DoWhile)):
        _check_expr_access(node.cond, held, conflict)
        return _walk_stmt(node.stmt, held, file_mutexes, conflict)
    if isinstance(node, c.DeclList):
        h = held
        for d in node.decls:
            h = _walk_stmt(d, h, file_mutexes, conflict)
        return h
    if isinstance(node, c.For):
        _walk_stmt(node.init, held, file_mutexes, conflict)
        _check_expr_access(node.cond, held, conflict)
        _walk_stmt(node.next, held, file_mutexes, conflict)
        return _walk_stmt(node.stmt, held, file_mutexes, conflict)
    if isinstance(node, c.Switch):
        _check_expr_access(node.cond, held, conflict)
        if not isinstance(node.stmt, c.Compound):
            return held
        join_h: str | None = held
        for it in node.stmt.block_items or []:
            if isinstance(it, (c.Case, c.Default)):
                stmts = it.stmts or []
                h_end = held
                for s in stmts:
                    h_end = _walk_stmt(s, h_end, file_mutexes, conflict)
                join_h = _join_held(join_h, h_end)
        return join_h
    if isinstance(node, (c.Break, c.Continue, c.Goto)):
        return held
    if isinstance(node, c.Return):
        _check_expr_access(node.expr, held, conflict)
        return held
    return held


def _verify_worker_mutex(
    ast: c.FileAST,
    fname: str,
    conflict: frozenset[str],
    file_mutexes: frozenset[str],
) -> None:
    if not conflict:
        return
    if not file_mutexes:
        raise MnemoCompileError(
            "due worker del PAR accedono agli stessi slot file-scope condivisi: "
            "serve almeno un `pthread_mutex_t` dichiarato a livello file "
            "(mutex locali ai worker non sincronizzano la memoria condivisa)."
        )
    fdef = _get_funcdef(ast, fname)
    if fdef is None or fdef.body is None:
        return
    _walk_stmt(fdef.body, None, file_mutexes, conflict)


def check_par_shared_mutex_discipline(
    ast: c.FileAST, layout: ProgramMemLayout
) -> None:
    """
    Solleva MnemoCompileError se due worker di un PAR referenziano gli stessi nomi
    di memoria file-scope condivisa senza disciplina mutex (lock su mutex globale).
    """
    shared = file_scope_shared_logical_names(layout)
    if not shared or not layout.parallel_file_shared_slots:
        return
    pairs = iter_par_worker_pairs(ast)
    if not pairs:
        return
    file_mutexes = frozenset(collect_file_scope_mutex_names(ast))
    for a, b in pairs:
        fa = _get_funcdef(ast, a)
        fb = _get_funcdef(ast, b)
        if fa is None or fb is None:
            continue
        sa = _refs_shared_in_function(fa, shared)
        sb = _refs_shared_in_function(fb, shared)
        conflict = frozenset(sa & sb)
        if not conflict:
            continue
        _verify_worker_mutex(ast, a, conflict, file_mutexes)
        _verify_worker_mutex(ast, b, conflict, file_mutexes)
