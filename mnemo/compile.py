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
) -> str:
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
