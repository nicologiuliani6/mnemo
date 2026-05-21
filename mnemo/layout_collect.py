"""
Calcolo statico del layout memoria unificata (__mn_mem0..) prima del lowering.
L'ordine di allocazione deve coincidere con _lower_stmt in c_lower.py.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import pycparser.c_ast as c

from mnemo.errors import MnemoCompileError


@dataclass(frozen=True)
class ProgramMemLayout:
    heap_base: int
    total_cells: int
    heap_cells: int
    slot_of: dict[tuple[str, str], int]
    ret_words: dict[str, int]
    """Nomi `int` a livello file con risultato sul secondo worker del PAR (main legge `__mn_mem{S+idx}`)."""
    file_scope_partition1: frozenset[str] = frozenset()
    """Funzioni usate solo come worker regione-1 (2° arg di parallel2, 1° di parallel_with*)."""
    parallel_region1_workers: frozenset[str] = frozenset()
    """Indici globali di variabili `("__file__", v)` con `v` non `__mn_p1_*`: stesso `__mn_mem{i}` in entrambi i rami PAR."""
    parallel_file_shared_slots: frozenset[int] = frozenset()
    """
    Locali `main` il cui valore aggiornato dopo `mnemo_pthread_parallel2` sta nella
    seconda partizione (`__mn_mem{S+idx}`): campi struct scritti solo dal worker 1 (secondo arg).
    """
    main_partition1_read_logicals: frozenset[str] = frozenset()


def _addr_of_root_var(expr: c.Node) -> str | None:
    """`&x` → `x`; altrimenti None."""
    if isinstance(expr, c.UnaryOp) and expr.op == "&":
        if isinstance(expr.expr, c.ID):
            return expr.expr.name
    return None


_MAX_PARTITION1_CALLEE_DEPTH = 16
# Nomi di funzioni ABI / runtime: nessun corpo C da seguire per l'inferenza.
_PARTITION1_SKIP_CALLEE_NAMES = frozenset(
    {
        "pthread_mutex_init",
        "pthread_mutex_lock",
        "pthread_mutex_unlock",
        "pthread_mutex_destroy",
        "mnemo_pthread_parallel2",
        "mnemo_pthread_start",
        "mnemo_pthread_start1",
        "mnemo_pthread_parallel_with",
        "mnemo_pthread_parallel_with1",
    }
)


def _flatten_funcall_args(call: c.FuncCall) -> list[c.Node]:
    if call.args is None:
        return []
    a = call.args
    if isinstance(a, c.ExprList):
        return list(a.exprs or [])
    return [a]


def _main_logical_from_worker_actual(
    expr: c.Node, worker_param_to_main: dict[str, str]
) -> str | None:
    """Espressione attuale → nome logico main (param worker mappato da parallel2)."""
    mv = _addr_of_root_var(expr)
    if mv is not None and mv in worker_param_to_main:
        return worker_param_to_main[mv]
    if isinstance(expr, c.ID) and expr.name in worker_param_to_main:
        return worker_param_to_main[expr.name]
    return None


def _partition1_follow_callee_call(
    call: c.FuncCall,
    param_to_main: dict[str, str],
    ast: c.FileAST,
    td: dict,
    struct_specs: dict,
    union_specs: dict,
    enum_constants: dict,
    depth: int,
    *,
    deref_acc: set[str] | None,
    struct_acc: set[str] | None,
) -> None:
    """Entra nel corpo di una funzione definita nello stesso AST (es. `srecv`)."""
    from mnemo import c_lower as L

    if depth >= _MAX_PARTITION1_CALLEE_DEPTH:
        return
    if not isinstance(call.name, c.ID):
        return
    fnm = call.name.name
    if fnm in _PARTITION1_SKIP_CALLEE_NAMES:
        return
    fdef = L._get_funcdef(ast, fnm)
    if fdef is None or not isinstance(fdef.decl.type, c.FuncDecl) or fdef.body is None:
        return
    inner = _callee_param_map_for_partition1(
        fdef.decl.type,
        call,
        param_to_main,
        td,
        struct_specs,
        union_specs,
        enum_constants,
    )
    if not inner:
        return
    if deref_acc is not None:
        _walk_assignments_deref_param(
            fdef.body,
            inner,
            deref_acc,
            ast,
            td,
            struct_specs,
            union_specs,
            enum_constants,
            depth + 1,
        )
    if struct_acc is not None:
        _walk_assignments_struct_arrow(
            fdef.body,
            inner,
            struct_acc,
            ast,
            td,
            struct_specs,
            union_specs,
            enum_constants,
            depth + 1,
        )


def _callee_param_map_for_partition1(
    callee_fd: c.FuncDecl,
    call: c.FuncCall,
    worker_param_to_main: dict[str, str],
    td: dict,
    struct_specs: dict,
    union_specs: dict,
    enum_constants: dict,
) -> dict[str, str]:
    """Mappa formali della callee → logici main (es. srecv(m,answer) con answer worker → main)."""
    from mnemo import c_lower as L

    pm = L._Ctx()
    pm.typedef_map = dict(td)
    pm.struct_specs = dict(struct_specs)
    pm.union_specs = dict(union_specs)
    pm.enum_constants = dict(enum_constants)
    pm.array_param_names = set()
    groups = L._func_param_slot_groups(callee_fd, td, pm)
    args = _flatten_funcall_args(call)
    if len(args) != len(groups):
        return {}
    inner: dict[str, str] = {}
    for group, rex in zip(groups, args):
        if len(group) != 1:
            continue
        fname = group[0]
        ml = _main_logical_from_worker_actual(rex, worker_param_to_main)
        if ml is not None:
            inner[fname] = ml
    return inner


def _partition1_follow_callee_call_arrow_fields(
    call: c.FuncCall,
    param_to_main: dict[str, str],
    ast: c.FileAST,
    td: dict,
    struct_specs: dict,
    union_specs: dict,
    enum_constants: dict,
    depth: int,
    out_fields: set[str],
) -> None:
    """Come _partition1_follow_callee_call, ma raccoglie `->campo` (primo segmento) in out_fields."""
    from mnemo import c_lower as L

    if depth >= _MAX_PARTITION1_CALLEE_DEPTH:
        return
    if not isinstance(call.name, c.ID):
        return
    fnm = call.name.name
    if fnm in _PARTITION1_SKIP_CALLEE_NAMES:
        return
    fdef = L._get_funcdef(ast, fnm)
    if fdef is None or not isinstance(fdef.decl.type, c.FuncDecl) or fdef.body is None:
        return
    inner = _callee_param_map_for_partition1(
        fdef.decl.type,
        call,
        param_to_main,
        td,
        struct_specs,
        union_specs,
        enum_constants,
    )
    if not inner:
        return
    _walk_arrow_field_first_segments(
        fdef.body,
        inner,
        out_fields,
        ast,
        td,
        struct_specs,
        union_specs,
        enum_constants,
        depth + 1,
    )


def _walk_expr_collect_arrow_field_segments(
    expr: c.Node | None,
    param_to_main: dict[str, str],
    out_fields: set[str],
) -> None:
    """Qualsiasi `param->campo` in un'espressione (es. rhs di `*p = m->payload`)."""
    from mnemo import c_lower as L

    if expr is None:
        return
    if isinstance(expr, c.StructRef) and expr.type == "->":
        base, parts = L._structref_base_and_path(expr)
        if base in param_to_main and len(parts) >= 1:
            out_fields.add(parts[0])
    for _na, ch in expr.children():
        if isinstance(ch, list):
            for x in ch:
                _walk_expr_collect_arrow_field_segments(x, param_to_main, out_fields)
        elif ch is not None:
            _walk_expr_collect_arrow_field_segments(ch, param_to_main, out_fields)


def _walk_arrow_field_first_segments(
    node: c.Node | None,
    param_to_main: dict[str, str],
    out_fields: set[str],
    ast: c.FileAST,
    td: dict,
    struct_specs: dict,
    union_specs: dict,
    enum_constants: dict,
    depth: int = 0,
) -> None:
    """Primi segmenti `base->campo` per inferenza PAR condivisa (anche dentro callee nello stesso file)."""
    from mnemo import c_lower as L

    if node is None or depth > _MAX_PARTITION1_CALLEE_DEPTH:
        return
    if isinstance(node, c.Compound):
        for it in node.block_items or []:
            _walk_arrow_field_first_segments(
                it,
                param_to_main,
                out_fields,
                ast,
                td,
                struct_specs,
                union_specs,
                enum_constants,
                depth,
            )
        return
    if isinstance(node, c.If):
        _walk_arrow_field_first_segments(
            node.iftrue,
            param_to_main,
            out_fields,
            ast,
            td,
            struct_specs,
            union_specs,
            enum_constants,
            depth,
        )
        _walk_arrow_field_first_segments(
            node.iffalse,
            param_to_main,
            out_fields,
            ast,
            td,
            struct_specs,
            union_specs,
            enum_constants,
            depth,
        )
        return
    if isinstance(node, c.For):
        _walk_arrow_field_first_segments(
            node.stmt,
            param_to_main,
            out_fields,
            ast,
            td,
            struct_specs,
            union_specs,
            enum_constants,
            depth,
        )
        return
    if isinstance(node, c.While):
        _walk_arrow_field_first_segments(
            node.stmt,
            param_to_main,
            out_fields,
            ast,
            td,
            struct_specs,
            union_specs,
            enum_constants,
            depth,
        )
        return
    if isinstance(node, c.DoWhile):
        _walk_arrow_field_first_segments(
            node.stmt,
            param_to_main,
            out_fields,
            ast,
            td,
            struct_specs,
            union_specs,
            enum_constants,
            depth,
        )
        return
    if isinstance(node, c.Switch) and isinstance(node.stmt, c.Compound):
        for it in node.stmt.block_items or []:
            if isinstance(it, c.Case):
                for s in it.stmts or []:
                    _walk_arrow_field_first_segments(
                        s,
                        param_to_main,
                        out_fields,
                        ast,
                        td,
                        struct_specs,
                        union_specs,
                        enum_constants,
                        depth,
                    )
            elif isinstance(it, c.Default):
                for s in it.stmts or []:
                    _walk_arrow_field_first_segments(
                        s,
                        param_to_main,
                        out_fields,
                        ast,
                        td,
                        struct_specs,
                        union_specs,
                        enum_constants,
                        depth,
                    )
        return
    if getattr(c, "ExprStmt", None) is not None and isinstance(node, c.ExprStmt):
        if node.expr is not None:
            _walk_arrow_field_first_segments(
                node.expr,
                param_to_main,
                out_fields,
                ast,
                td,
                struct_specs,
                union_specs,
                enum_constants,
                depth,
            )
        return
    if isinstance(node, c.FuncCall):
        _partition1_follow_callee_call_arrow_fields(
            node,
            param_to_main,
            ast,
            td,
            struct_specs,
            union_specs,
            enum_constants,
            depth,
            out_fields,
        )
        return
    if isinstance(node, c.Assignment):
        lv = node.lvalue
        if isinstance(lv, c.StructRef) and lv.type == "->":
            base, parts = L._structref_base_and_path(lv)
            if base in param_to_main and len(parts) >= 1:
                out_fields.add(parts[0])
        _walk_expr_collect_arrow_field_segments(
            node.rvalue, param_to_main, out_fields
        )
        return


def _collect_arrow_field_names_for_param_deep(
    body: c.Node | None,
    param: str,
    main_root: str,
    ast: c.FileAST,
    td: dict,
    struct_specs: dict,
    union_specs: dict,
    enum_constants: dict,
) -> set[str]:
    """Campi `param->campo` nel corpo del worker e nelle funzioni dello stesso file (es. ssend/srecv)."""
    param_to_main = {param: main_root}
    out: set[str] = set()
    _walk_arrow_field_first_segments(
        body,
        param_to_main,
        out,
        ast,
        td,
        struct_specs,
        union_specs,
        enum_constants,
        0,
    )
    return out


def _walk_collect_parallel2_calls(node: c.Node | None, out: list[c.FuncCall]) -> None:
    if node is None:
        return
    if isinstance(node, c.Compound):
        for it in node.block_items or []:
            _walk_collect_parallel2_calls(it, out)
        return
    if isinstance(node, c.If):
        _walk_collect_parallel2_calls(node.iftrue, out)
        _walk_collect_parallel2_calls(node.iffalse, out)
        return
    if isinstance(node, c.For):
        _walk_collect_parallel2_calls(node.stmt, out)
        return
    if isinstance(node, c.While):
        _walk_collect_parallel2_calls(node.stmt, out)
        return
    if isinstance(node, c.DoWhile):
        _walk_collect_parallel2_calls(node.stmt, out)
        return
    if isinstance(node, c.Switch) and isinstance(node.stmt, c.Compound):
        for it in node.stmt.block_items or []:
            if isinstance(it, c.Case):
                for s in it.stmts or []:
                    _walk_collect_parallel2_calls(s, out)
            elif isinstance(it, c.Default):
                for s in it.stmts or []:
                    _walk_collect_parallel2_calls(s, out)
        return
    if isinstance(node, c.FuncCall) and isinstance(node.name, c.ID):
        if node.name.name == "mnemo_pthread_parallel2":
            out.append(node)
        return


def _walk_assignments_deref_param(
    node: c.Node | None,
    param_to_main: dict[str, str],
    out_logicals: set[str],
    ast: c.FileAST,
    td: dict,
    struct_specs: dict,
    union_specs: dict,
    enum_constants: dict,
    depth: int = 0,
) -> None:
    """
    Assegnamenti `*param = …` dove `param` è un puntatore formale del worker 1
    mappato a `&variabile_main` (es. `*answer = …` con `&answer` nella parallel2).
    Segue anche chiamate a funzioni definite nello stesso file (es. `srecv(m, answer)`).
    """
    if node is None or depth > _MAX_PARTITION1_CALLEE_DEPTH:
        return
    if isinstance(node, c.Compound):
        for it in node.block_items or []:
            _walk_assignments_deref_param(
                it,
                param_to_main,
                out_logicals,
                ast,
                td,
                struct_specs,
                union_specs,
                enum_constants,
                depth,
            )
        return
    if isinstance(node, c.If):
        _walk_assignments_deref_param(
            node.iftrue, param_to_main, out_logicals, ast, td, struct_specs, union_specs, enum_constants, depth
        )
        _walk_assignments_deref_param(
            node.iffalse, param_to_main, out_logicals, ast, td, struct_specs, union_specs, enum_constants, depth
        )
        return
    if isinstance(node, c.For):
        _walk_assignments_deref_param(
            node.stmt, param_to_main, out_logicals, ast, td, struct_specs, union_specs, enum_constants, depth
        )
        return
    if isinstance(node, c.While):
        _walk_assignments_deref_param(
            node.stmt, param_to_main, out_logicals, ast, td, struct_specs, union_specs, enum_constants, depth
        )
        return
    if isinstance(node, c.DoWhile):
        _walk_assignments_deref_param(
            node.stmt, param_to_main, out_logicals, ast, td, struct_specs, union_specs, enum_constants, depth
        )
        return
    if isinstance(node, c.Switch) and isinstance(node.stmt, c.Compound):
        for it in node.stmt.block_items or []:
            if isinstance(it, c.Case):
                for s in it.stmts or []:
                    _walk_assignments_deref_param(
                        s, param_to_main, out_logicals, ast, td, struct_specs, union_specs, enum_constants, depth
                    )
            elif isinstance(it, c.Default):
                for s in it.stmts or []:
                    _walk_assignments_deref_param(
                        s, param_to_main, out_logicals, ast, td, struct_specs, union_specs, enum_constants, depth
                    )
        return
    if getattr(c, "ExprStmt", None) is not None and isinstance(node, c.ExprStmt):
        if node.expr is not None:
            _walk_assignments_deref_param(
                node.expr,
                param_to_main,
                out_logicals,
                ast,
                td,
                struct_specs,
                union_specs,
                enum_constants,
                depth,
            )
        return
    if isinstance(node, c.FuncCall):
        _partition1_follow_callee_call(
            node,
            param_to_main,
            ast,
            td,
            struct_specs,
            union_specs,
            enum_constants,
            depth,
            deref_acc=out_logicals,
            struct_acc=None,
        )
        return
    if isinstance(node, c.Assignment):
        lv = node.lvalue
        if (
            isinstance(lv, c.UnaryOp)
            and lv.op == "*"
            and isinstance(lv.expr, c.ID)
        ):
            pname = lv.expr.name
            if pname in param_to_main:
                out_logicals.add(param_to_main[pname])
        return


def _walk_assignments_struct_arrow(
    node: c.Node | None,
    param_to_main: dict[str, str],
    out_logicals: set[str],
    ast: c.FileAST,
    td: dict,
    struct_specs: dict,
    union_specs: dict,
    enum_constants: dict,
    depth: int = 0,
) -> None:
    from mnemo import c_lower as L

    if node is None or depth > _MAX_PARTITION1_CALLEE_DEPTH:
        return
    if isinstance(node, c.Compound):
        for it in node.block_items or []:
            _walk_assignments_struct_arrow(
                it, param_to_main, out_logicals, ast, td, struct_specs, union_specs, enum_constants, depth
            )
        return
    if isinstance(node, c.If):
        _walk_assignments_struct_arrow(
            node.iftrue, param_to_main, out_logicals, ast, td, struct_specs, union_specs, enum_constants, depth
        )
        _walk_assignments_struct_arrow(
            node.iffalse, param_to_main, out_logicals, ast, td, struct_specs, union_specs, enum_constants, depth
        )
        return
    if isinstance(node, c.For):
        _walk_assignments_struct_arrow(
            node.stmt, param_to_main, out_logicals, ast, td, struct_specs, union_specs, enum_constants, depth
        )
        return
    if isinstance(node, c.While):
        _walk_assignments_struct_arrow(
            node.stmt, param_to_main, out_logicals, ast, td, struct_specs, union_specs, enum_constants, depth
        )
        return
    if isinstance(node, c.DoWhile):
        _walk_assignments_struct_arrow(
            node.stmt, param_to_main, out_logicals, ast, td, struct_specs, union_specs, enum_constants, depth
        )
        return
    if isinstance(node, c.Switch) and isinstance(node.stmt, c.Compound):
        for it in node.stmt.block_items or []:
            if isinstance(it, c.Case):
                for s in it.stmts or []:
                    _walk_assignments_struct_arrow(
                        s, param_to_main, out_logicals, ast, td, struct_specs, union_specs, enum_constants, depth
                    )
            elif isinstance(it, c.Default):
                for s in it.stmts or []:
                    _walk_assignments_struct_arrow(
                        s, param_to_main, out_logicals, ast, td, struct_specs, union_specs, enum_constants, depth
                    )
        return
    if getattr(c, "ExprStmt", None) is not None and isinstance(node, c.ExprStmt):
        if node.expr is not None:
            _walk_assignments_struct_arrow(
                node.expr,
                param_to_main,
                out_logicals,
                ast,
                td,
                struct_specs,
                union_specs,
                enum_constants,
                depth,
            )
        return
    if isinstance(node, c.FuncCall):
        _partition1_follow_callee_call(
            node,
            param_to_main,
            ast,
            td,
            struct_specs,
            union_specs,
            enum_constants,
            depth,
            deref_acc=None,
            struct_acc=out_logicals,
        )
        return
    if isinstance(node, c.Assignment):
        lv = node.lvalue
        if isinstance(lv, c.StructRef) and lv.type == "->":
            base, parts = L._structref_base_and_path(lv)
            if base in param_to_main and len(parts) >= 1:
                main_v = param_to_main[base]
                out_logicals.add(L._struct_field_local(main_v, parts[0]))
        return


def _infer_parallel_shared_main_slots(
    ast: c.FileAST,
    slot_of: dict[tuple[str, str], int],
    td: dict,
    struct_specs: dict,
    union_specs: dict,
    enum_constants: dict,
) -> set[int]:
    """
    Se lo stesso `&variabile_main` è passato a entrambi i worker PAR e entrambi usano
    `p->campo` sulla struct, quelle celle devono essere la stessa __mn_mem{i} in entrambi
    i rami (non partizioni distinte), altrimenti pool_load/store non comunicano.
    """
    from mnemo import c_lower as L

    main_ext = L._find_main(ast)
    if main_ext is None or main_ext.body is None or not isinstance(
        main_ext.body, c.Compound
    ):
        return set()

    calls: list[c.FuncCall] = []
    for it in main_ext.body.block_items or []:
        _walk_collect_parallel2_calls(it, calls)

    idx_out: set[int] = set()
    for call in calls:
        el = call.args
        exprs = list(el.exprs) if el is not None else []
        if len(exprs) < 2:
            continue
        if not isinstance(exprs[0], c.ID) or not isinstance(exprs[1], c.ID):
            continue
        f0, f1 = exprs[0].name, exprs[1].name
        fdef0 = L._get_funcdef(ast, f0)
        fdef1 = L._get_funcdef(ast, f1)
        if fdef0 is None or fdef1 is None:
            continue
        fd0 = fdef0.decl.type
        fd1 = fdef1.decl.type
        if not isinstance(fd0, c.FuncDecl) or not isinstance(fd1, c.FuncDecl):
            continue
        pm0 = L._Ctx()
        pm0.typedef_map = dict(td)
        pm0.struct_specs = dict(struct_specs)
        pm0.union_specs = dict(union_specs)
        pm0.enum_constants = dict(enum_constants)
        pm0.array_param_names = set()
        pm1 = L._Ctx()
        pm1.typedef_map = dict(td)
        pm1.struct_specs = dict(struct_specs)
        pm1.union_specs = dict(union_specs)
        pm1.enum_constants = dict(enum_constants)
        pm1.array_param_names = set()
        g0 = L._func_param_slot_groups(fd0, td, pm0)
        g1 = L._func_param_slot_groups(fd1, td, pm1)
        if len(exprs) != 2 + len(g0) + len(g1):
            continue
        raw0 = exprs[2 : 2 + len(g0)]
        raw1 = exprs[2 + len(g0) :]
        if len(raw0) != len(g0) or len(raw1) != len(g1):
            continue
        body0 = fdef0.body
        body1 = fdef1.body
        if body0 is None or body1 is None:
            continue
        for i in range(min(len(g0), len(g1))):
            if len(g0[i]) != 1 or len(g1[i]) != 1:
                continue
            p0, p1 = g0[i][0], g1[i][0]
            mv0 = _addr_of_root_var(raw0[i])
            mv1 = _addr_of_root_var(raw1[i])
            if mv0 is None or mv0 != mv1:
                continue
            fields0 = _collect_arrow_field_names_for_param_deep(
                body0, p0, mv0, ast, td, struct_specs, union_specs, enum_constants
            )
            fields1 = _collect_arrow_field_names_for_param_deep(
                body1, p1, mv1, ast, td, struct_specs, union_specs, enum_constants
            )
            for fn in fields0 & fields1:
                logical = L._struct_field_local(mv0, fn)
                key = ("main", logical)
                if key in slot_of:
                    idx_out.add(slot_of[key])
    return idx_out


def _infer_main_partition1_read_logicals(
    ast: c.FileAST,
    slot_of: dict[tuple[str, str], int],
    td: dict,
    struct_specs: dict,
    union_specs: dict,
    enum_constants: dict,
) -> frozenset[str]:
    """
    Dopo `mnemo_pthread_parallel2(f,g, args_f..., args_g...)`, il ramo destro usa
    `__mn_mem{S+idx}`. In main, dopo il PAR, vanno letti dalla partizione 1 i valori
    aggiornati in g tramite `p->campo = ...` oppure `*param = ...` con `param` legato a
    `&variabile_main` negli argomenti del secondo worker. Gli stessi effetti vengono
    riconosciuti anche se avvengono in funzioni helper nello stesso file (es. `srecv`).
    """
    from mnemo import c_lower as L

    main_ext = L._find_main(ast)
    if main_ext is None or main_ext.body is None or not isinstance(
        main_ext.body, c.Compound
    ):
        return frozenset()

    calls: list[c.FuncCall] = []
    for it in main_ext.body.block_items or []:
        _walk_collect_parallel2_calls(it, calls)

    acc: set[str] = set()
    for call in calls:
        el = call.args
        exprs = list(el.exprs) if el is not None else []
        if len(exprs) < 2:
            continue
        if not isinstance(exprs[0], c.ID) or not isinstance(exprs[1], c.ID):
            continue
        f0, f1 = exprs[0].name, exprs[1].name
        fdef0 = L._get_funcdef(ast, f0)
        fdef1 = L._get_funcdef(ast, f1)
        if fdef0 is None or fdef1 is None:
            continue
        fd0 = fdef0.decl.type
        fd1 = fdef1.decl.type
        if not isinstance(fd0, c.FuncDecl) or not isinstance(fd1, c.FuncDecl):
            continue
        pm0 = L._Ctx()
        pm0.typedef_map = dict(td)
        pm0.struct_specs = dict(struct_specs)
        pm0.union_specs = dict(union_specs)
        pm0.enum_constants = dict(enum_constants)
        pm0.array_param_names = set()
        pm1 = L._Ctx()
        pm1.typedef_map = dict(td)
        pm1.struct_specs = dict(struct_specs)
        pm1.union_specs = dict(union_specs)
        pm1.enum_constants = dict(enum_constants)
        pm1.array_param_names = set()
        g0 = L._func_param_slot_groups(fd0, td, pm0)
        g1 = L._func_param_slot_groups(fd1, td, pm1)
        if len(exprs) != 2 + len(g0) + len(g1):
            continue
        raw1 = exprs[2 + len(g0) :]
        if len(raw1) != len(g1):
            continue
        param_to_main: dict[str, str] = {}
        for group, rex in zip(g1, raw1):
            if len(group) != 1:
                continue
            p = group[0]
            mv = _addr_of_root_var(rex)
            if mv is not None:
                param_to_main[p] = mv
        if not param_to_main:
            continue
        body1 = fdef1.body
        if body1 is None:
            continue
        _walk_assignments_struct_arrow(
            body1, param_to_main, acc, ast, td, struct_specs, union_specs, enum_constants
        )
        _walk_assignments_deref_param(
            body1, param_to_main, acc, ast, td, struct_specs, union_specs, enum_constants
        )

    verified: set[str] = set()
    for log in acc:
        if ("main", log) in slot_of:
            verified.add(log)
    return frozenset(verified)


def compute_program_mem_layout(
    ast: c.FileAST, heap_pool_cells: int
) -> ProgramMemLayout:
    from mnemo import c_lower as L

    td, specs, unions, enums = L.collect_file_typedefs_structs_unions_enums(ast)
    slot_of: dict[tuple[str, str], int] = {}
    # Slot 0 riservato come "sentinel NULL": `int *p = NULL` ≡ p = 0, e
    # `&v` di una variabile reale non collide mai con NULL. Senza la
    # riserva, la prima variabile finiva su slot 0 → `if (p) {...}` falso.
    cursor = 1
    ret_words: dict[str, int] = {}

    def alloc(fn: str, logical: str) -> None:
        nonlocal cursor
        slot_of[(fn, logical)] = cursor
        cursor += 1

    def sizeof_ret(fd: c.FuncDecl) -> int:
        mini = L._Ctx(
            typedef_map=dict(td),
            struct_specs=dict(specs),
            union_specs=dict(unions),
            enum_constants=dict(enums),
        )
        return L._sizeof_return_bytes(fd, mini)

    def walk_decl(node: c.Decl, fn: str, ctx: L._Ctx) -> None:
        if isinstance(node.type, c.Union):
            un = node.type
            if un.decls and un.name:
                ctx.union_specs[un.name] = L._union_scalar_fields(un)
            return

        if isinstance(node.type, c.Enum) and node.type.values:
            ctx.enum_constants.update(L._enum_constants_from_enum(node.type))
            return

        if isinstance(node.type, c.Struct):
            st = node.type
            if st.decls and st.name:
                ctx.struct_specs[st.name] = L._flatten_struct_fields(st)
            return

        ut = L._union_tag_for_decl_type(node.type, ctx)
        if ut is not None:
            if not isinstance(node.type, c.TypeDecl) or node.type.declname is None:
                raise MnemoCompileError("union: nome variabile mancante")
            varname = str(node.type.declname)
            logical = L._scope_declare(ctx, varname)
            if ut not in ctx.union_specs:
                raise MnemoCompileError(f"union {ut}: definizione mancante")
            ctx.union_tag_of_var[logical] = ut
            ctx.int_locals.add(logical)
            alloc(fn, logical)
            return

        st_tag = L._struct_tag_for_decl_type(node.type, ctx)
        if st_tag is not None:
            if not isinstance(node.type, c.TypeDecl) or node.type.declname is None:
                raise MnemoCompileError("struct: nome variabile mancante")
            varname = str(node.type.declname)
            logical = L._scope_declare(ctx, varname)
            fields = ctx.struct_specs.get(st_tag)
            if not fields:
                raise MnemoCompileError(f"struct {st_tag}: definizione mancante")
            ctx.struct_tag_of_var[logical] = st_tag
            for fnm, fty in fields:
                if L._type_node_is_pthread_mutex(fty, ctx.typedef_map):
                    continue
                loc = L._struct_field_local(logical, fnm)
                ctx.int_locals.add(loc)
                alloc(fn, loc)
            return

        ap = L._try_parse_array_decl(node, ctx)
        if ap is not None:
            name, dims, esz = ap
            tot = int(math.prod(dims))
            logical = L._scope_declare(ctx, name)
            ctx.array_info[logical] = L._ArrayInfo(dims=dims, total=tot, elem_size=esz)
            for i in range(tot):
                cell = L._array_elem_local(logical, i)
                ctx.int_locals.add(cell)
                alloc(fn, cell)
            return

        imm_td = L._immediate_named_scalar_typedef(node)
        if imm_td == "pthread_mutex_t":
            if not isinstance(node.type, c.TypeDecl) or node.type.declname is None:
                raise MnemoCompileError("pthread_mutex_t: nome variabile mancante")
            varname = str(node.type.declname)
            logical = L._scope_declare(ctx, varname)
            ctx.int_locals.add(logical)
            return
        if imm_td == "mnemo_kairos_channel_t":
            if not isinstance(node.type, c.TypeDecl) or node.type.declname is None:
                raise MnemoCompileError("mnemo_kairos_channel_t: nome variabile mancante")
            varname = str(node.type.declname)
            logical = L._scope_declare(ctx, varname)
            ctx.int_locals.add(logical)
            return

        tdm = ctx.typedef_map
        name = L._scalar_decl_name(node, tdm)
        if name is None:
            name = L._enum_scalar_decl_name(node)
        if name is None:
            fp_meta = L._func_ptr_decl_meta(node, tdm)
            if fp_meta is not None:
                fp_name, _cfd = fp_meta
                logical_fp = L._scope_declare(ctx, fp_name)
                ctx.int_locals.add(logical_fp)
                ctx.func_ptr_vars.add(logical_fp)
                alloc(fn, logical_fp)
                return
            pn = L._int_ptr_var_decl_name(node, tdm)
            if pn is None:
                pn = L._struct_pointer_param_name(node, ctx)
            if pn is None:
                raise MnemoCompileError(
                    f"dichiarazione non supportata: {type(node.type).__name__}"
                )
            name = pn
            ros = L._char_ptr_string_literal_meta(node, tdm, fn)
            if ros is not None:
                _ros_meta_base, tot, _raw = ros
                logical = L._scope_declare(ctx, name)
                sbase = f"__mn_ros_{fn}_{logical}"
                if sbase in ctx.array_info:
                    raise MnemoCompileError(f"ridichiarazione: {sbase}")
                ctx.array_info[sbase] = L._ArrayInfo(
                    dims=(tot,), total=tot, elem_size=1
                )
                for i in range(tot):
                    cell = L._array_elem_local(sbase, i)
                    if cell in ctx.int_locals:
                        raise MnemoCompileError(f"ridichiarazione: {cell}")
                    ctx.int_locals.add(cell)
                    alloc(fn, cell)
                ctx.int_locals.add(logical)
                alloc(fn, logical)
                return
        logical = L._scope_declare(ctx, name)
        ctx.int_locals.add(logical)
        alloc(fn, logical)

    def walk_stmt(node: c.Node | None, fn: str, ctx: L._Ctx) -> None:
        if node is None:
            return
        if isinstance(node, c.EmptyStatement):
            return
        if isinstance(node, c.Typedef):
            ctx.typedef_map[node.name] = node.type
            L._maybe_register_struct_from_typedef(
                node.name, node.type, ctx.struct_specs
            )
            L._maybe_register_union_from_typedef(
                node.name, node.type, ctx.union_specs
            )
            u = L._strip_typedecl(node.type)
            if isinstance(u, c.Enum) and u.values:
                ctx.enum_constants.update(L._enum_constants_from_enum(u))
            return
        if isinstance(node, c.Decl):
            walk_decl(node, fn, ctx)
            return
        if isinstance(node, c.Compound):
            L._scope_enter(ctx)
            for sub in node.block_items or []:
                walk_stmt(sub, fn, ctx)
            L._scope_exit(ctx)
            return
        if isinstance(node, c.If):
            walk_stmt(node.iftrue, fn, ctx)
            walk_stmt(node.iffalse, fn, ctx)
            return
        if isinstance(node, c.While):
            walk_stmt(node.stmt, fn, ctx)
            return
        if isinstance(node, c.DoWhile):
            walk_stmt(node.stmt, fn, ctx)
            return
        if isinstance(node, c.For):
            needs_scope = isinstance(node.init, (c.Decl, c.DeclList))
            if needs_scope:
                L._scope_enter(ctx)
            try:
                walk_for_init(node.init, fn, ctx)
                walk_stmt(node.stmt, fn, ctx)
            finally:
                if needs_scope:
                    L._scope_exit(ctx)
            return
        if isinstance(node, c.Switch):
            if not isinstance(node.stmt, c.Compound):
                raise MnemoCompileError("switch: il corpo deve essere { ... }")
            for it in node.stmt.block_items or []:
                if isinstance(it, c.Case):
                    for s in it.stmts or []:
                        walk_stmt(s, fn, ctx)
                elif isinstance(it, c.Default):
                    for s in it.stmts or []:
                        walk_stmt(s, fn, ctx)
            return

    def walk_for_init(init: c.Node | None, fn: str, ctx: L._Ctx) -> None:
        if init is None:
            return
        if isinstance(init, c.DeclList):
            for decl in init.decls:
                walk_stmt(decl, fn, ctx)
            return
        if isinstance(init, (c.Decl, c.Assignment)):
            walk_stmt(init, fn, ctx)

    def collect_function(fname: str, fd: c.FuncDecl, body: c.Compound | None) -> None:
        nonlocal ret_words
        ctx = L._Ctx()
        ctx.typedef_map = td
        ctx.struct_specs = specs
        ctx.union_specs = unions
        ctx.enum_constants = enums
        ctx.int_locals = set()
        ctx.array_info = {}
        ctx.struct_tag_of_var = {}
        ctx.union_tag_of_var = {}
        ctx.array_param_names = set()
        for p in L._func_param_storage_names(fd, td, ctx):
            alloc(fname, p)
        rw = L._return_words_from_bytes(sizeof_ret(fd))
        ret_words[fname] = rw
        for rn in L._ret_slot_names(rw):
            alloc(fname, rn)
        if body is not None:
            L._scope_init_params(ctx, tuple(L._func_param_storage_names(fd, td, ctx)))
            for sub in body.block_items or []:
                walk_stmt(sub, fname, ctx)

    file_par1: set[str] = set()
    fs_ctx = L._Ctx()
    fs_ctx.typedef_map = td
    fs_ctx.struct_specs = specs
    fs_ctx.union_specs = unions
    fs_ctx.enum_constants = enums
    for ext in ast.ext:
        if isinstance(ext, c.FuncDef):
            continue
        if isinstance(ext, c.Typedef):
            continue
        if not isinstance(ext, c.Decl):
            continue
        if isinstance(ext.type, c.FuncDecl):
            continue
        # `extern T name;` forward declaration: la definizione vera è altrove
        # (un altro Decl più avanti nello stesso file, o un'altra TU che Mnemo
        # non supporta). Skip per evitare "variabile file-scope duplicata".
        if ext.storage and "extern" in ext.storage and ext.init is None:
            continue
        imm = L._immediate_named_scalar_typedef(ext)
        if imm in ("pthread_mutex_t", "mnemo_kairos_channel_t"):
            continue

        ut = L._union_tag_for_decl_type(ext.type, fs_ctx)
        if ut is not None:
            if not isinstance(ext.type, c.TypeDecl) or ext.type.declname is None:
                raise MnemoCompileError("union: nome variabile mancante")
            varname = str(ext.type.declname)
            if varname in fs_ctx.int_locals:
                raise MnemoCompileError(f"ridichiarazione: {varname}")
            if ut not in fs_ctx.union_specs:
                raise MnemoCompileError(f"union {ut}: definizione mancante")
            fs_ctx.union_tag_of_var[varname] = ut
            fs_ctx.int_locals.add(varname)
            if ("__file__", varname) in slot_of:
                raise MnemoCompileError(f"variabile file-scope duplicata: {varname}")
            alloc("__file__", varname)
            if varname.startswith("__mn_p1_"):
                file_par1.add(varname)
            continue

        st_tag = L._struct_tag_for_decl_type(ext.type, fs_ctx)
        if st_tag is not None:
            if not isinstance(ext.type, c.TypeDecl) or ext.type.declname is None:
                raise MnemoCompileError("struct: nome variabile mancante")
            varname = str(ext.type.declname)
            if varname in fs_ctx.int_locals:
                raise MnemoCompileError(f"ridichiarazione: {varname}")
            fields = fs_ctx.struct_specs.get(st_tag)
            if not fields:
                raise MnemoCompileError(f"struct {st_tag}: definizione mancante")
            fs_ctx.struct_tag_of_var[varname] = st_tag
            for fnm, fty in fields:
                if L._type_node_is_pthread_mutex(fty, td):
                    continue
                loc = L._struct_field_local(varname, fnm)
                if loc in fs_ctx.int_locals:
                    raise MnemoCompileError(f"ridichiarazione: {loc}")
                fs_ctx.int_locals.add(loc)
                if ("__file__", loc) in slot_of:
                    raise MnemoCompileError(f"variabile file-scope duplicata: {loc}")
                alloc("__file__", loc)
                if loc.startswith("__mn_p1_"):
                    file_par1.add(loc)
            continue

        ap = L._try_parse_array_decl(ext, fs_ctx)
        if ap is not None:
            name, dims, esz = ap
            tot = int(math.prod(dims))
            if name in fs_ctx.int_locals:
                raise MnemoCompileError(f"ridichiarazione file-scope: {name}")
            fs_ctx.array_info[name] = L._ArrayInfo(
                dims=dims, total=tot, elem_size=esz
            )
            for i in range(tot):
                cell = L._array_elem_local(name, i)
                if cell in fs_ctx.int_locals:
                    raise MnemoCompileError(f"ridichiarazione: {cell}")
                fs_ctx.int_locals.add(cell)
                if ("__file__", cell) in slot_of:
                    raise MnemoCompileError(
                        f"variabile file-scope duplicata: {cell}"
                    )
                alloc("__file__", cell)
                if cell.startswith("__mn_p1_"):
                    file_par1.add(cell)
            continue
        tdm = td
        name = L._scalar_decl_name(ext, tdm)
        if name is None:
            name = L._enum_scalar_decl_name(ext)
        if name is None:
            pn = L._int_ptr_var_decl_name(ext, tdm)
            if pn is None:
                continue
            name = pn
            if L._char_ptr_string_literal_meta(ext, tdm, "__file__") is not None:
                raise MnemoCompileError(
                    "char* = letterale a livello file non supportato "
                    "(sposta la dichiarazione in main o in una funzione)"
                )
        if ("__file__", name) in slot_of:
            raise MnemoCompileError(f"variabile file-scope duplicata: {name}")
        alloc("__file__", name)
        if name.startswith("__mn_p1_"):
            file_par1.add(name)

    for ext in ast.ext:
        if isinstance(ext, c.FuncDef) and ext.decl.name and ext.decl.name != "main":
            fd = ext.decl.type
            if isinstance(fd, c.FuncDecl):
                collect_function(
                    ext.decl.name,
                    fd,
                    ext.body if isinstance(ext.body, c.Compound) else None,
                )

    main_ext = L._find_main(ast)
    if main_ext is None:
        raise MnemoCompileError("nessuna funzione int main(...) trovata")
    mfd = main_ext.decl.type
    if not isinstance(mfd, c.FuncDecl):
        raise MnemoCompileError("main malformato")
    ctx_main = L._Ctx()
    ctx_main.typedef_map = td
    ctx_main.struct_specs = specs
    ctx_main.union_specs = unions
    ctx_main.enum_constants = enums
    ctx_main.int_locals = set()
    ctx_main.array_info = {}
    ctx_main.struct_tag_of_var = {}
    ctx_main.union_tag_of_var = {}
    ctx_main.array_param_names = set()
    for name, _role in L._main_locals_from_fd(mfd):
        alloc("main", name)
    ret_words["main"] = 0
    body = main_ext.body
    if body is not None and isinstance(body, c.Compound):
        L._scope_init_params(
            ctx_main, [name for name, _ in L._main_locals_from_fd(mfd)]
        )
        for sub in body.block_items or []:
            walk_stmt(sub, "main", ctx_main)

    heap_base = cursor
    total = heap_base + heap_pool_cells
    parallel_shared_slots: set[int] = set()
    for (fn, logical), idx in slot_of.items():
        if fn == "__file__" and not logical.startswith("__mn_p1_"):
            parallel_shared_slots.add(idx)
    parallel_shared_slots.update(
        _infer_parallel_shared_main_slots(
            ast, slot_of, td, specs, unions, enums
        )
    )
    main_p1_reads = _infer_main_partition1_read_logicals(
        ast, slot_of, td, specs, unions, enums
    )
    return ProgramMemLayout(
        heap_base=heap_base,
        total_cells=total,
        heap_cells=heap_pool_cells,
        slot_of=slot_of,
        ret_words=ret_words,
        file_scope_partition1=frozenset(file_par1),
        parallel_region1_workers=L.infer_parallel_region1_workers(ast),
        parallel_file_shared_slots=frozenset(parallel_shared_slots),
        main_partition1_read_logicals=main_p1_reads,
    )
