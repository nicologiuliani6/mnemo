"""C → .kairos: parse, lower, emit, prelude lib/."""

from __future__ import annotations

from mnemo.c_lower import (
    PTHREAD_ABI_TWO_REGION_PAR,
    _convert_kr_to_ansi,
    _hoist_compound_literals_in_ast,
    _hoist_static_locals,
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
    # `int f(...) { switch(...) { case A: return V; ... } }` → single-return.
    _transform_switch_returns(ast)
    # `int f(...) { if (c1) return E1; else if (c2) return E2; ... }` → single-return.
    _transform_if_chain_returns(ast)
    # `int f(...) { if (c) return E1; ...; return E2; }` → single-return.
    _transform_early_return_if_then_return(ast)
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
