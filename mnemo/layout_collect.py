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


def compute_program_mem_layout(
    ast: c.FileAST, heap_pool_cells: int
) -> ProgramMemLayout:
    from mnemo import c_lower as L

    td, specs, unions, enums = L.collect_file_typedefs_structs_unions_enums(ast)
    slot_of: dict[tuple[str, str], int] = {}
    cursor = 0
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
            if varname in ctx.int_locals or varname in ctx.array_info:
                raise MnemoCompileError(f"ridichiarazione: {varname}")
            if ut not in ctx.union_specs:
                raise MnemoCompileError(f"union {ut}: definizione mancante")
            ctx.union_tag_of_var[varname] = ut
            ctx.int_locals.add(varname)
            alloc(fn, varname)
            return

        st_tag = L._struct_tag_for_decl_type(node.type, ctx)
        if st_tag is not None:
            if not isinstance(node.type, c.TypeDecl) or node.type.declname is None:
                raise MnemoCompileError("struct: nome variabile mancante")
            varname = str(node.type.declname)
            if varname in ctx.int_locals or varname in ctx.array_info:
                raise MnemoCompileError(f"ridichiarazione: {varname}")
            fields = ctx.struct_specs.get(st_tag)
            if not fields:
                raise MnemoCompileError(f"struct {st_tag}: definizione mancante")
            ctx.struct_tag_of_var[varname] = st_tag
            for fnm, _fty in fields:
                loc = L._struct_field_local(varname, fnm)
                ctx.int_locals.add(loc)
                alloc(fn, loc)
            return

        ap = L._try_parse_array_decl(node, ctx)
        if ap is not None:
            name, dims, esz = ap
            tot = int(math.prod(dims))
            if name in ctx.array_info or name in ctx.int_locals:
                raise MnemoCompileError(f"ridichiarazione: {name}")
            ctx.array_info[name] = L._ArrayInfo(dims=dims, total=tot, elem_size=esz)
            for i in range(tot):
                cell = L._array_elem_local(name, i)
                ctx.int_locals.add(cell)
                alloc(fn, cell)
            return

        if isinstance(node.type, c.TypeDecl) and node.type.declname is not None:
            imm = node.type.type
            if isinstance(imm, c.IdentifierType) and len(imm.names) == 1:
                if imm.names[0] == "pthread_mutex_t":
                    varname = str(node.type.declname)
                    if varname in ctx.int_locals or varname in ctx.array_info:
                        raise MnemoCompileError(f"ridichiarazione: {varname}")
                    ctx.int_locals.add(varname)
                    return

        tdm = ctx.typedef_map
        name = L._scalar_decl_name(node, tdm)
        if name is None:
            name = L._enum_scalar_decl_name(node)
        if name is None:
            pn = L._int_ptr_var_decl_name(node, tdm)
            if pn is None:
                raise MnemoCompileError(
                    f"dichiarazione non supportata: {type(node.type).__name__}"
                )
            name = pn
        if name in ctx.int_locals or name in ctx.array_info:
            raise MnemoCompileError(f"ridichiarazione: {name}")
        ctx.int_locals.add(name)
        alloc(fn, name)

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
            for sub in node.block_items or []:
                walk_stmt(sub, fn, ctx)
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
            walk_for_init(node.init, fn, ctx)
            walk_stmt(node.stmt, fn, ctx)
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
            walk_stmt(body, fname, ctx)

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
        imm = L._immediate_named_scalar_typedef(ext)
        if imm == "pthread_mutex_t":
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
            for fnm, _fty in fields:
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

        if L._try_parse_array_decl(ext, fs_ctx) is not None:
            raise MnemoCompileError(
                "variabile a livello file: solo scalari `int`/typedef supportati (niente array)"
            )
        tdm = td
        name = L._scalar_decl_name(ext, tdm)
        if name is None:
            name = L._enum_scalar_decl_name(ext)
        if name is None:
            pn = L._int_ptr_var_decl_name(ext, tdm)
            if pn is None:
                continue
            name = pn
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
        walk_stmt(body, "main", ctx_main)

    heap_base = cursor
    total = heap_base + heap_pool_cells
    parallel_shared_slots: set[int] = set()
    for (fn, logical), idx in slot_of.items():
        if fn == "__file__" and not logical.startswith("__mn_p1_"):
            parallel_shared_slots.add(idx)
    return ProgramMemLayout(
        heap_base=heap_base,
        total_cells=total,
        heap_cells=heap_pool_cells,
        slot_of=slot_of,
        ret_words=ret_words,
        file_scope_partition1=frozenset(file_par1),
        parallel_region1_workers=L.infer_parallel_region1_workers(ast),
        parallel_file_shared_slots=frozenset(parallel_shared_slots),
    )
