"""
Lowering pycparser AST → IR Mnemo.

- `int main(void)`; altre funzioni `void|int|unsigned|bool|_Bool` con corpo C → procedure Kairos.
- Convenzione ritorno: valore non-void → slot `__mn_ret` o `__mn_ret0`…; precall azzera gli slot di ritorno; post-call copia nel chiamante.
- Tipi scalari (tutti `int` in Kairos): int, unsigned int, unsigned, _Bool, bool.
- Espressioni: letterali, ID, + - * / %, unario -, `sizeof` (tipo o variabile, valore intero calcolato a compile-time), cast verso scalari, chiamate `int f()` come espressione.
- Controllo: `if` (anche `&&`/`||`), `while`/`do…while`/`for`, `break`/`continue` nei cicli, `switch`/`case`.
- `int main(int argc, char **argv)`: `argc` da `// mnemo-main-argc: N` (default 0 se assente); `argv` è stub `int` = 0 (non usabile come puntatore).
- Assegnamenti `+=`, `-=`, `*=`, `/=`, `%=`.
- Pool `malloc`/`free`: dimensione N con `mnemo compile --ptr-pool-size N` (default 4, max 256); genera `__mn_mem0`…`__mn_mem{N-1}` e le procedure `__mn_pool_*` in Kairos.
- Array: `int a[N]`, multidimensionale `int m[R][C]`, array di puntatori `int *p[K]` / `void *v[K]`; indici row-major; max 256 elementi totali; init `{…}` piatto o annidato.
- Tipi scalari: int, unsigned/uint (unsigned int), bool/_Bool; `typedef`; `enum` (costanti intere);
  `struct` (campi scalari, sott-struct annidate in linea); `union` (solo membri scalari, stesso int);
  passaggio `int a[N]` come `int*`.
- Espr.: operatore ternario `?:`, virgola (anche in `int x = (a, b);` come `ExprList`), XOR `^` e `^=`.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import pycparser.c_ast as c

from mnemo.errors import MnemoCompileError
from mnemo.layout_collect import ProgramMemLayout, compute_program_mem_layout
from mnemo.ptr_pool_kairos import PTR_POOL_MAX
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
    IPar,
    IReturn,
    ISrecv,
    ISsend,
    IShow,
    ISubEq,
    IXorEq,
    Instr,
    Program,
    Imm,
    Var,
)

BUILTIN_KAIROS_PROCS = frozenset(
    {
        "__mn_mul_into",
        "__mn_divmod_nonneg",
        "__mn_mod_nonneg",
        "__mn_pool_alloc",
        "__mn_pool_store",
        "__mn_pool_load",
        "__mn_pool_free",
    }
)

# ABI C “pthread” / π-calculus: lowering diretto (non sono procedure Kairos).
PTHREAD_ABI_NAMES = frozenset(
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

PTHREAD_ABI_TWO_REGION_PAR = frozenset(
    {
        "mnemo_pthread_parallel2",
        "mnemo_pthread_parallel_with",
        "mnemo_pthread_parallel_with1",
    }
)


def _func_body_uses_two_region_parallel(ast: c.FileAST, fname: str) -> bool:
    """Il corpo di `fname` contiene un ABI PAR a due rami che richiede due finestre __mn_mem."""
    for ext in ast.ext:
        if not isinstance(ext, c.FuncDef) or ext.decl.name != fname:
            continue
        stack: list[c.Node | None] = [ext.body]
        while stack:
            n = stack.pop()
            if n is None:
                continue
            if isinstance(n, c.FuncCall) and isinstance(n.name, c.ID):
                if n.name.name in PTHREAD_ABI_TWO_REGION_PAR:
                    return True
            for _na, ch in n.children():
                if isinstance(ch, list):
                    stack.extend(ch)
                elif ch is not None:
                    stack.append(ch)
        return False
    return False


def infer_parallel_region1_workers(ast: c.FileAST) -> frozenset[str]:
    """
    Worker che usa la finestra memoria «regione 1» (S..2S-1): secondo argomento di
    `mnemo_pthread_parallel2`, primo argomento di `parallel_with` / `parallel_with1`.
    """
    out: set[str] = set()
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
                a1 = exprs[1]
                if isinstance(a1, c.ID):
                    out.add(a1.name)
            elif nm in (
                "mnemo_pthread_parallel_with",
                "mnemo_pthread_parallel_with1",
            ) and exprs:
                a0 = exprs[0]
                if isinstance(a0, c.ID):
                    out.add(a0.name)
        for _na, ch in n.children():
            if isinstance(ch, list):
                stack.extend(ch)
            elif ch is not None:
                stack.append(ch)
    return frozenset(out)


def _func_reads_partition1_file_vars(
    ast: c.FileAST, fname: str, par1: frozenset[str]
) -> bool:
    if not par1:
        return False
    fdef = _get_funcdef(ast, fname)
    if fdef is None or fdef.body is None:
        return False
    stack: list[c.Node | None] = [fdef.body]
    while stack:
        n = stack.pop()
        if n is None:
            continue
        if isinstance(n, c.ID) and n.name in par1:
            return True
        for _na, ch in n.children():
            if isinstance(ch, list):
                stack.extend(ch)
            elif ch is not None:
                stack.append(ch)
    return False


# Contatore pool; le celle sono `__mn_mem0` … `__mn_mem{N-1}` con N = `ctx.ptr_pool_size`.
_PTR_POOL_CTR = "__mn_pool_ctr"

MN_RET = "__mn_ret"

_CMP_OPS: frozenset[str] = frozenset({"==", "!=", "<", "<=", ">", ">="})

# Modello statico `sizeof` (byte): LP32-like; in Kairos resta solo un intero costante.
_SIZEOF_CHAR = 1
_SIZEOF_SCALAR = 4
_SIZEOF_POINTER = 4

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


def _strip_typedecl(node: c.Node) -> c.Node:
    cur: c.Node = node
    while isinstance(cur, c.TypeDecl):
        cur = cur.type
    return cur


def _follow_typedef_chain(
    names: list[str], td: dict[str, c.Node], seen: set[str]
) -> c.Node:
    """Segue `typedef` fino a un nodo non-Identificatore (Struct, PtrDecl, …)."""
    if len(names) != 1:
        return c.IdentifierType(names, coord=None)  # type: ignore[call-arg]
    n = names[0]
    if n not in td:
        return c.IdentifierType(names, coord=None)  # type: ignore[call-arg]
    if n in seen:
        raise MnemoCompileError(f"typedef circolare: {n!r}")
    seen.add(n)
    root = td[n]
    while isinstance(root, c.TypeDecl):
        root = root.type
    if isinstance(root, c.IdentifierType):
        return _follow_typedef_chain(list(root.names), td, seen)
    return root


def _expand_typedef_names(names: list[str], td: dict[str, c.Node]) -> list[str]:
    leaf = _follow_typedef_chain(names, td, set())
    if isinstance(leaf, c.IdentifierType):
        return list(leaf.names)
    if isinstance(leaf, c.Enum):
        return ["int"]
    raise MnemoCompileError(
        f"tipo non scalare in contesto che richiede nomi scalari: {type(leaf).__name__}"
    )


def _is_scalar_type_names(names: list[str], td: dict[str, c.Node]) -> bool:
    try:
        ex = _expand_typedef_names(names, td)
    except MnemoCompileError:
        return False
    return tuple(ex) in _SCALAR_NAMES


def _flatten_struct_fields(st: c.Struct, prefix: str = "") -> list[tuple[str, c.Node]]:
    """Campi struct con annidamento inline: `struct { int y; } n` → `prefix+n__y`."""
    out: list[tuple[str, c.Node]] = []
    for d in st.decls or []:
        if not isinstance(d, c.Decl) or not d.name:
            continue
        fname = str(d.name)
        cur = _strip_typedecl(d.type)
        if isinstance(cur, c.Struct) and cur.decls:
            out.extend(_flatten_struct_fields(cur, prefix + fname + "__"))
        else:
            out.append((prefix + fname, d.type))
    if not out:
        raise MnemoCompileError("struct: almeno un campo richiesto")
    return out


def _union_flat_fields(un: c.Union, prefix: str = "") -> list[tuple[str, c.Node]]:
    """Campi union appiattiti (struct/union annidati come per struct)."""
    out: list[tuple[str, c.Node]] = []
    for d in un.decls or []:
        if not isinstance(d, c.Decl) or not d.name:
            continue
        fname = str(d.name)
        inner = _strip_typedecl(d.type)
        if isinstance(inner, c.Struct) and inner.decls:
            out.extend(_flatten_struct_fields(inner, prefix + fname + "__"))
        elif isinstance(inner, c.Union) and inner.decls:
            out.extend(_union_flat_fields(inner, prefix + fname + "__"))
        else:
            out.append((prefix + fname, d.type))
    if not out:
        raise MnemoCompileError("union: almeno un campo richiesto")
    return out


def _union_scalar_fields(un: c.Union) -> list[tuple[str, c.Node]]:
    return _union_flat_fields(un)


def _maybe_register_struct_from_typedef(name: str, type_node: c.Node, specs: dict[str, list[tuple[str, c.Node]]]) -> None:
    u = _strip_typedecl(type_node)
    if isinstance(u, c.Struct) and u.decls:
        tag = u.name if u.name else name
        specs[tag] = _flatten_struct_fields(u)


def _maybe_register_union_from_typedef(
    name: str, type_node: c.Node, union_specs: dict[str, list[tuple[str, c.Node]]]
) -> None:
    u = _strip_typedecl(type_node)
    if isinstance(u, c.Union) and u.decls:
        tag = u.name if u.name else name
        union_specs[tag] = _union_scalar_fields(u)


def collect_file_typedefs_structs_unions_enums(
    ast: c.FileAST,
) -> tuple[
    dict[str, c.Node],
    dict[str, list[tuple[str, c.Node]]],
    dict[str, list[tuple[str, c.Node]]],
    dict[str, int],
]:
    td: dict[str, c.Node] = {}
    specs: dict[str, list[tuple[str, c.Node]]] = {}
    union_specs: dict[str, list[tuple[str, c.Node]]] = {}
    enums: dict[str, int] = {}
    for ext in ast.ext:
        if isinstance(ext, c.Typedef):
            td[ext.name] = ext.type
            _maybe_register_struct_from_typedef(ext.name, ext.type, specs)
            _maybe_register_union_from_typedef(ext.name, ext.type, union_specs)
            u = _strip_typedecl(ext.type)
            if isinstance(u, c.Enum) and u.values:
                enums.update(_enum_constants_from_enum(u))
        elif isinstance(ext, c.Decl) and isinstance(ext.type, c.Struct):
            st = ext.type
            if st.decls and st.name:
                specs[st.name] = _flatten_struct_fields(st)
        elif isinstance(ext, c.Decl) and isinstance(ext.type, c.Union):
            un = ext.type
            if un.decls and un.name:
                union_specs[un.name] = _union_scalar_fields(un)
        elif isinstance(ext, c.Decl) and isinstance(ext.type, c.Enum):
            en = ext.type
            if en.values:
                enums.update(_enum_constants_from_enum(en))
    return td, specs, union_specs, enums


def collect_file_typedefs_and_structs(
    ast: c.FileAST,
) -> tuple[dict[str, c.Node], dict[str, list[tuple[str, c.Node]]]]:
    td, specs, _, _ = collect_file_typedefs_structs_unions_enums(ast)
    return td, specs


def _enum_constants_from_enum(en: c.Enum) -> dict[str, int]:
    cur = 0
    out: dict[str, int] = {}
    for ev in en.values.enumerators:
        if ev.value is not None:
            cur = _const_int(ev.value)
        out[ev.name] = cur
        cur += 1
    return out


@dataclass
class _ArrayInfo:
    """Row-major: `dims` = (d0,d1,…), `total` = ∏ dims, `elem_size` byte per elemento."""

    dims: tuple[int, ...]
    total: int
    elem_size: int = _SIZEOF_SCALAR


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
    """Tipo C dichiarato (`Decl.type`) per `sizeof nome`."""
    var_types: dict[str, c.Node] = field(default_factory=dict)
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
    loop_ct_i: int = 0
    """Numero di celle `__mn_mem*` nel pool (parametro compile `--ptr-pool-size`)."""
    ptr_pool_size: int = 4
    """Metadati array: dimensioni e numero totale di celle (indice lineare row-major)."""
    array_info: dict[str, _ArrayInfo] = field(default_factory=dict)
    typedef_map: dict[str, c.Node] = field(default_factory=dict)
    struct_specs: dict[str, list[tuple[str, c.Node]]] = field(default_factory=dict)
    """Variabile C → tag struct per `sizeof(v)` e accessi campo."""
    struct_tag_of_var: dict[str, str] = field(default_factory=dict)
    """Parametri dichiarati come `int a[]` / `int a[N]` (decay a puntatore)."""
    array_param_names: set[str] = field(default_factory=set)
    union_specs: dict[str, list[tuple[str, c.Node]]] = field(default_factory=dict)
    union_tag_of_var: dict[str, str] = field(default_factory=dict)
    enum_constants: dict[str, int] = field(default_factory=dict)
    """Layout programma (memoria unificata)."""
    mem_layout: ProgramMemLayout | None = None
    fn_name: str = "main"
    total_mem_cells: int = 4
    """Celle `__mn_mem*` dichiarate nel frame (>= layout.total_cells se due partizioni par)."""
    physical_mem_cells: int = 4
    heap_base: int = 0
    mem_phys: dict[str, str] = field(default_factory=dict)
    slot_index: dict[str, int] = field(default_factory=dict)
    ret_vars: list[str] = field(default_factory=list)
    proc_ret_words: dict[str, int] = field(default_factory=dict)
    defined_user_functions: frozenset[str] = field(default_factory=frozenset)
    file_ast: c.FileAST | None = None
    """Ordine dei parametri formali (nomi storage) per snapshot tra due chiamate in `f()+g()`."""
    param_storage_order: tuple[str, ...] = ()
    channel_kairos: dict[str, str] = field(default_factory=dict)
    channel_decl_order: list[str] = field(default_factory=list)
    # Mutex `pthread_mutex_t` a livello file (nomi C ordinati) → formali Kairos `channel` in coda.
    file_scope_mutex_names: tuple[str, ...] = ()
    """Dopo `mnemo_pthread_parallel2` in main: letture campi worker-1 usano la 2ª partizione."""
    after_par_join: bool = False

    def fresh_temp(self) -> str:
        name = f"__mn_e{self.temp_i}"
        self.temp_i += 1
        self.int_locals.add(name)
        return name

    def fresh_loop_ct(self) -> str:
        """
        Variabile solo per `ILocalBlock` (continue): `local int`/`delocal` nel corpo del loop.
        Non va in `int_locals` così non c'è `int __mn_*` a livello procedura omonimo del `local` annidato.
        """
        name = f"__mn_lc{self.loop_ct_i}"
        self.loop_ct_i += 1
        return name


def _ptr_pool_mem_names(ctx: _Ctx) -> tuple[str, ...]:
    n = ctx.total_mem_cells if ctx.mem_layout is not None else ctx.ptr_pool_size
    return tuple(f"__mn_mem{i}" for i in range(n))


def _parallel_branch_mem_actuals(ctx: _Ctx, *, left: bool) -> list[str]:
    """
    Argomenti `call f(__mn_mem*, …)` per un ramo PAR a due worker.
    - Indici in `layout.parallel_file_shared_slots`: stesso actual `__mn_mem{i}` (memoria file-scope condivisa).
    - Altrimenti: ramo sinistro `__mn_mem{i}`, destro `__mn_mem{S+i}` (finestre disgiunte).
    """
    if ctx.mem_layout is None:
        raise MnemoCompileError("layout memoria mancante (parallel)")
    s = ctx.mem_layout.total_cells
    shared = ctx.mem_layout.parallel_file_shared_slots
    base = 0 if left else s
    out: list[str] = []
    for i in range(s):
        if i in shared:
            out.append(f"__mn_mem{i}")
        else:
            out.append(f"__mn_mem{base + i}")
    if 2 * s > ctx.physical_mem_cells:
        raise MnemoCompileError(
            "partizioni memoria parallele: celle fisiche insufficienti "
            f"(serve physical_mem_cells >= {2 * s})"
        )
    return out


def _pool_call_slot_arg(
    ctx: _Ctx, phys_slot: str
) -> tuple[list[Instr], str, list[str]]:
    """
    Le procedure __mn_pool_* prendono (slot, …, __mn_mem0, …).
    Se slot è lo stesso nome di una cella mem, i parametri aliasano → IR Kairos non reversibile.
    Copia il valore dello slot in un temporaneo quando serve.
    """
    mems = _ptr_pool_mem_names(ctx)
    if phys_slot not in mems:
        return [], phys_slot, []
    t = ctx.fresh_temp()
    ctx.use_hist = True
    return (
        [IHistPush(ctx.hist, t), IAddEq(t, Var(phys_slot))],
        t,
        [t],
    )


def _phys(ctx: _Ctx, logical: str) -> str:
    """
    Nome Kairos per una variabile logica (cella __mn_mem{idx}).
    Variabili file-scope `("__file__", name)`: `__mn_p1_*` nel worker regione-1
    usano il formale `__mn_mem{idx}`; in main e nel resto usano `__mn_mem{S+idx}`.
    """
    hit = ctx.mem_phys.get(logical)
    if hit is not None:
        if (
            ctx.fn_name == "main"
            and ctx.after_par_join
            and ctx.mem_layout is not None
            and (
                logical in ctx.mem_layout.main_partition1_read_logicals
                or logical in ctx.mem_layout.file_scope_partition1
            )
        ):
            idx = ctx.slot_index.get(logical)
            if idx is not None:
                s = ctx.mem_layout.total_cells
                return f"__mn_mem{s + idx}"
        # Parametri procedure utente: finestra pool __mn_mem0..S-1. Le altre variabili
        # (es. `acc`, `i`) usano gli stessi indici globali → collisione di nome con il formale.
        if (
            not ctx.is_main
            and ctx.param_storage_order
            and logical not in ctx.param_storage_order
        ):
            suf = hit[8:] if hit.startswith("__mn_mem") else ""
            if (
                hit.startswith("__mn_mem")
                and suf.isdigit()
                and int(suf) < ctx.total_mem_cells
            ):
                alt = f"__mn_v_{logical}"
                ctx.int_locals.add(alt)
                if alt not in ctx.decl_order:
                    ctx.decl_order.append(alt)
                return alt
        return hit
    key = ("__file__", logical)
    if ctx.mem_layout is not None and key in ctx.mem_layout.slot_of:
        idx = ctx.mem_layout.slot_of[key]
        s = ctx.mem_layout.total_cells
        if logical in ctx.mem_layout.file_scope_partition1:
            if ctx.fn_name in ctx.mem_layout.parallel_region1_workers:
                return f"__mn_mem{idx}"
            return f"__mn_mem{s + idx}"
        return f"__mn_mem{idx}"
    return logical


def _sizeof_return_bytes(fd: c.FuncDecl, mini: _Ctx) -> int:
    if _func_return_is_void(fd):
        return 0
    return _sizeof_of_c_type_node(fd.type, mini)


def _return_words_from_bytes(nbytes: int) -> int:
    if nbytes <= 0:
        return 0
    return (nbytes + _SIZEOF_SCALAR - 1) // _SIZEOF_SCALAR


def _ret_slot_names(n_words: int) -> list[str]:
    if n_words <= 0:
        return []
    if n_words == 1:
        return [MN_RET]
    return [f"__mn_ret{i}" for i in range(n_words)]


# Limite elementi totali per array (prodotto delle dimensioni; IR a catena if sull’indice lineare).
ARR_MAX = 1024


def _array_elem_local(base: str, linear: int) -> str:
    return f"__mn_arr_{base}_{linear}"


def _array_dim_const(dim: c.Node | None) -> int:
    if dim is None:
        raise MnemoCompileError("array: dimensione mancante")
    if isinstance(dim, c.Constant):
        n = _const_int(dim)
        if n < 1:
            raise MnemoCompileError("array: dimensione >= 1")
        return n
    raise MnemoCompileError("array: la dimensione deve essere una costante intera")


def _decl_basename_from_innermost(cur: c.Node) -> str | None:
    """Nome dopo eventuale PtrDecl esterno (es. `int *p[4]` → PtrDecl → TypeDecl p)."""
    if isinstance(cur, c.PtrDecl):
        cur = cur.type
    if isinstance(cur, c.TypeDecl) and cur.declname is not None:
        return str(cur.declname)
    return None


def _sizeof_array_element_type(cur: c.Node, ctx: _Ctx) -> int | None:
    """
    Byte sizeof di un elemento array. Scalari Mnemo o puntatore a scalare/void (un solo `*`).
    """
    td = ctx.typedef_map
    if isinstance(cur, c.PtrDecl):
        inn = cur.type
        if isinstance(inn, c.PtrDecl):
            return None
        if isinstance(inn, c.TypeDecl) and isinstance(inn.type, c.IdentifierType):
            nms = list(inn.type.names)
            if nms == ["void"] or nms == ["int"]:
                return _SIZEOF_POINTER
            if _is_scalar_type_names(nms, td):
                return _SIZEOF_POINTER
        return None
    if isinstance(cur, c.TypeDecl) and isinstance(cur.type, c.IdentifierType):
        return _sizeof_of_c_type_node(cur, ctx)
    return None


def _try_parse_array_decl(
    node: c.Decl, ctx: _Ctx
) -> tuple[str, tuple[int, ...], int] | None:
    """
    Ritorna `(nome, dims, sizeof_elemento)` per dichiarazioni array, altrimenti `None`.
    """
    cur = node.type
    dims: list[int] = []
    while isinstance(cur, c.ArrayDecl):
        dims.append(_array_dim_const(cur.dim))
        cur = cur.type
    if not dims:
        return None
    esz = _sizeof_array_element_type(cur, ctx)
    if esz is None:
        raise MnemoCompileError(
            "array: elemento supportato solo se scalare Mnemo o puntatore "
            "(int/unsigned/bool/…, int*, void*)"
        )
    name = _decl_basename_from_innermost(cur)
    if name is None:
        return None
    tot = int(math.prod(dims))
    if tot > ARR_MAX:
        raise MnemoCompileError(
            f"array: al massimo {ARR_MAX} elementi totali (prodotto dimensioni), qui {tot}"
        )
    return name, tuple(dims), esz


def _flatten_array_ref_chain(expr: c.Node) -> tuple[str, list[c.Node]]:
    """Es. `a[i][j]` → (`'a'`, `[i, j]`) in ordine row-major C."""
    subs: list[c.Node] = []
    cur: c.Node = expr
    while isinstance(cur, c.ArrayRef):
        subs.insert(0, cur.subscript)
        cur = cur.name
    if not isinstance(cur, c.ID):
        raise MnemoCompileError("array: la base dell'indicizzazione deve essere un nome")
    return cur.name, subs


def _c_row_major_index_ast(
    subs: list[c.Node], dims: tuple[int, ...], coord
) -> c.Node:
    """Espressione C per indice lineare row-major."""
    if len(subs) != len(dims):
        raise MnemoCompileError("array: numero di indici errato")
    if not subs:
        raise MnemoCompileError("array: indici mancanti")
    terms: list[c.Node] = []
    for i, s in enumerate(subs):
        stride = int(math.prod(dims[i + 1 :])) if i + 1 < len(dims) else 1
        if stride == 1:
            terms.append(s)
        else:
            terms.append(
                c.BinaryOp(
                    "*",
                    s,
                    c.Constant("int", str(stride)),
                    coord,
                )
            )
    acc: c.Node = terms[0]
    for t in terms[1:]:
        acc = c.BinaryOp("+", acc, t, coord)
    return acc


def _const_row_major_linear(subs: list[c.Node], dims: tuple[int, ...]) -> int | None:
    """Se tutti gli indici sono costanti, ritorna l'indice lineare; altrimenti `None`."""
    if len(subs) != len(dims):
        return None
    parts: list[int] = []
    for i, s in enumerate(subs):
        if not isinstance(s, c.Constant):
            return None
        k = _const_int(s)
        if k < 0 or k >= dims[i]:
            raise MnemoCompileError(
                f"indice costante {k} fuori da [0,{dims[i] - 1}] (dim {i})"
            )
        parts.append(k)
    lin = 0
    for i in range(len(dims)):
        lin = lin * dims[i] + parts[i]
    return lin


def _flatten_init_list(init: c.InitList) -> list[c.Node]:
    """Init annidato `{{a,b},{c}}` → lista piatta in ordine row-major."""
    out: list[c.Node] = []
    for e in init.exprs:
        if isinstance(e, c.InitList):
            out.extend(_flatten_init_list(e))
        else:
            out.append(e)
    return out


def _fold_exprlist_as_comma_chain(el: c.ExprList) -> c.Node:
    """`(a, b, c)` nel parser è spesso `ExprList`, equivalente a catena di `,`."""
    if len(el.exprs) == 1:
        return el.exprs[0]
    acc: c.Node = el.exprs[0]
    for e in el.exprs[1:]:
        acc = c.BinaryOp(",", acc, e, el.coord)
    return acc


def _disj_eq_chain(
    disc: str, values: list[int], bodies: list[list[Instr]]
) -> list[Instr]:
    """if disc==v0 then body0 else (if disc==v1 then …) — come switch su interi."""
    assert len(values) == len(bodies) and values

    def rec(i: int) -> list[Instr]:
        if i >= len(values):
            return []
        tail = rec(i + 1)
        else_b = tail if tail else None
        return [IIfKairos(disc, "==", str(values[i]), bodies[i], else_b)]

    return rec(0)


def _scalar_decl_name(node: c.Decl, td: dict[str, c.Node]) -> str | None:
    t = node.type
    if not isinstance(t, c.TypeDecl):
        return None
    inner = t.type
    if not isinstance(inner, c.IdentifierType):
        return None
    if not _is_scalar_type_names(inner.names, td):
        return None
    if t.declname is None:
        return None
    return str(t.declname)


def _immediate_named_scalar_typedef(decl: c.Decl) -> str | None:
    """Es. `typedef int pthread_mutex_t` + `pthread_mutex_t m` → `pthread_mutex_t`."""
    if not isinstance(decl.type, c.TypeDecl) or decl.type.declname is None:
        return None
    inner = decl.type.type
    if isinstance(inner, c.IdentifierType) and len(inner.names) == 1:
        return inner.names[0]
    return None


def collect_file_scope_mutex_names(ast: c.FileAST) -> tuple[str, ...]:
    """Nomi C di `pthread_mutex_t` a livello file (un canale Kairos condiviso tra worker)."""
    out: list[str] = []
    for ext in ast.ext:
        if isinstance(ext, (c.FuncDef, c.Typedef)):
            continue
        if not isinstance(ext, c.Decl):
            continue
        if isinstance(ext.type, c.FuncDecl):
            continue
        if _immediate_named_scalar_typedef(ext) != "pthread_mutex_t":
            continue
        if not isinstance(ext.type, c.TypeDecl) or ext.type.declname is None:
            continue
        out.append(str(ext.type.declname))
    return tuple(sorted(out))


def _file_scope_channel_actuals(ctx: _Ctx) -> list[str]:
    return [ctx.channel_kairos[m] for m in ctx.file_scope_mutex_names]


def _pthread_mutex_ptr_name(arg: c.Node) -> str:
    if isinstance(arg, c.UnaryOp) and arg.op == "&" and isinstance(arg.expr, c.ID):
        return arg.expr.name
    raise MnemoCompileError("pthread_mutex_*: atteso &mutex (variabile pthread_mutex_t)")


def _pthread_assign_worker_first_scalar_arg(
    fname: str,
    arg_expr: c.Node,
    ctx: _Ctx,
    *,
    mem_partition_index: int = 0,
) -> list[Instr]:
    """
    Marshalling del primo argomento scalare verso lo slot __mn_mem del worker
    (start1 / parallel_with1). `mem_partition_index` 0 = base 0; 1 = seconda
    partizione (`__mn_mem{S+idx}`) quando il worker gira nel ramo PAR isolato.
    """
    if ctx.file_ast is None or ctx.mem_layout is None:
        raise MnemoCompileError("worker con argomento scalare: contesto senza layout o AST")
    fdef = _get_funcdef(ctx.file_ast, fname)
    if fdef is None:
        raise MnemoCompileError(f"worker con argomento scalare: {fname!r} non è definita nel file")
    fd = fdef.decl.type
    if not isinstance(fd, c.FuncDecl):
        raise MnemoCompileError("worker con argomento scalare: firma worker non valida")
    pm = _Ctx()
    pm.typedef_map = dict(ctx.typedef_map)
    pm.struct_specs = dict(ctx.struct_specs)
    pm.union_specs = dict(ctx.union_specs)
    pm.enum_constants = dict(ctx.enum_constants)
    pm.array_param_names = set()
    param_names = _func_param_storage_names(fd, ctx.typedef_map, pm)
    if len(param_names) != 1:
        raise MnemoCompileError(
            "worker con argomento scalare: serve esattamente un parametro scalare "
            "(es. `void t(int x)`; niente struct/void)"
        )
    log = param_names[0]
    key = (fname, log)
    if key not in ctx.mem_layout.slot_of:
        raise MnemoCompileError("worker con argomento scalare: slot parametro mancante nel layout")
    idx = ctx.mem_layout.slot_of[key]
    s = ctx.mem_layout.total_cells
    phys = mem_partition_index * s + idx
    dst = f"__mn_mem{phys}"
    return _lower_assign(dst, arg_expr, ctx)


def _pthread_assign_worker_params(
    fname: str,
    raw_exprs: list[c.Node],
    ctx: _Ctx,
    *,
    mem_partition_index: int,
) -> list[Instr]:
    """
    Copia gli argomenti del caller nello spazio memoria del worker PAR (stesso schema
    delle chiamate utente: struct per valore, più slot, puntatori, ecc.).
    `mem_partition_index` 0 = ramo sinistro, 1 = destro (`__mn_mem{S+idx}`).
    """
    if ctx.file_ast is None or ctx.mem_layout is None:
        raise MnemoCompileError("worker PAR: layout memoria mancante")
    fdef = _get_funcdef(ctx.file_ast, fname)
    if fdef is None:
        raise MnemoCompileError(f"worker PAR: {fname!r} non è definita nel file")
    fd = fdef.decl.type
    if not isinstance(fd, c.FuncDecl):
        raise MnemoCompileError("worker PAR: firma non valida")
    pm = _Ctx()
    pm.typedef_map = dict(ctx.typedef_map)
    pm.struct_specs = dict(ctx.struct_specs)
    pm.union_specs = dict(ctx.union_specs)
    pm.enum_constants = dict(ctx.enum_constants)
    pm.array_param_names = set()
    groups = _func_param_slot_groups(fd, ctx.typedef_map, pm)
    param_logs = _func_param_storage_names(fd, ctx.typedef_map, pm)
    if len(groups) != len(raw_exprs):
        raise MnemoCompileError(
            f"worker `{fname}`: servono {len(groups)} argomenti formali, ne ho {len(raw_exprs)}"
        )
    layout = ctx.mem_layout
    lead_arg, flat_exprs = _flatten_user_call_arguments(
        raw_exprs, groups, ctx, layout
    )
    if len(flat_exprs) != len(param_logs):
        raise MnemoCompileError(
            f"worker `{fname}`: mismatch tra argomenti appiattiti e slot nel layout"
        )
    s = layout.total_cells
    pre: list[Instr] = []
    pre.extend(lead_arg)
    for ex, log_key in zip(flat_exprs, param_logs):
        key = (fname, log_key)
        if key not in layout.slot_of:
            raise MnemoCompileError(
                f"worker `{fname}`: slot parametro {log_key!r} assente nel layout"
            )
        idx = layout.slot_of[key]
        phys = mem_partition_index * s + idx
        dst = f"__mn_mem{phys}"
        pre.extend(_lower_assign(dst, ex, ctx))
    return pre


def _pthread_worker_has_no_params(fname: str, ctx: _Ctx) -> bool:
    if ctx.file_ast is None:
        return False
    fdef = _get_funcdef(ctx.file_ast, fname)
    if fdef is None:
        return False
    fd = fdef.decl.type
    if not isinstance(fd, c.FuncDecl):
        return False
    pm = _Ctx()
    pm.typedef_map = dict(ctx.typedef_map)
    pm.struct_specs = dict(ctx.struct_specs)
    pm.union_specs = dict(ctx.union_specs)
    pm.enum_constants = dict(ctx.enum_constants)
    pm.array_param_names = set()
    names = _func_param_storage_names(fd, ctx.typedef_map, pm)
    return len(names) == 0


def _lower_pthread_mnemo_call(node: c.FuncCall, ctx: _Ctx) -> list[Instr] | None:
    """Ritorna istruzioni se è una chiamata ABI pthread/π; altrimenti None."""
    if not isinstance(node.name, c.ID):
        return None
    nm = node.name.name
    if nm not in PTHREAD_ABI_NAMES:
        return None
    el = node.args
    exprs = list(el.exprs) if el is not None else []

    if nm == "mnemo_pthread_start":
        if ctx.mem_layout is None:
            raise MnemoCompileError("mnemo_pthread_start: layout memoria mancante")
        if len(exprs) != 1:
            raise MnemoCompileError(
                "mnemo_pthread_start(void (*f)(void)): atteso 1 argomento (nome funzione)"
            )
        a0 = exprs[0]
        if not isinstance(a0, c.ID):
            raise MnemoCompileError("mnemo_pthread_start: passare il nome della funzione")
        f0 = a0.name
        if f0 not in ctx.defined_user_functions:
            raise MnemoCompileError(
                "mnemo_pthread_start: la funzione deve essere definita nel file"
            )
        if not _pthread_worker_has_no_params(f0, ctx):
            raise MnemoCompileError(
                "mnemo_pthread_start: il worker deve essere `void f(void)` (nessun parametro)"
            )
        mem_args = [f"__mn_mem{i}" for i in range(ctx.mem_layout.total_cells)]
        chx = _file_scope_channel_actuals(ctx)
        return [IPar([[ICall(f0, mem_args + chx)]])]

    if nm == "mnemo_pthread_start1":
        if ctx.mem_layout is None:
            raise MnemoCompileError("mnemo_pthread_start1: layout memoria mancante")
        if len(exprs) != 2:
            raise MnemoCompileError(
                "mnemo_pthread_start1(void (*f)(void), int arg): servono 2 argomenti"
            )
        a0, a1 = exprs[0], exprs[1]
        if not isinstance(a0, c.ID):
            raise MnemoCompileError("mnemo_pthread_start1: passare il nome della funzione come primo argomento")
        f0 = a0.name
        if f0 not in ctx.defined_user_functions:
            raise MnemoCompileError(
                "mnemo_pthread_start1: la funzione deve essere definita nel file"
            )
        pre = _pthread_assign_worker_first_scalar_arg(f0, a1, ctx)
        mem_args = [f"__mn_mem{i}" for i in range(ctx.mem_layout.total_cells)]
        chx = _file_scope_channel_actuals(ctx)
        ctx.use_hist = True
        return pre + [IPar([[ICall(f0, mem_args + chx)]])]

    if nm == "mnemo_pthread_parallel_with":
        if ctx.mem_layout is None:
            raise MnemoCompileError("mnemo_pthread_parallel_with: layout memoria mancante")
        if len(exprs) != 2:
            raise MnemoCompileError(
                "mnemo_pthread_parallel_with(void (*worker)(void), void (*cont)(void)): "
                "servono 2 argomenti"
            )
        a0, a1 = exprs[0], exprs[1]
        if not isinstance(a0, c.ID) or not isinstance(a1, c.ID):
            raise MnemoCompileError(
                "mnemo_pthread_parallel_with: passare i nomi delle funzioni (void (*)(void))"
            )
        f_work, f_cont = a0.name, a1.name
        if f_work not in ctx.defined_user_functions or f_cont not in ctx.defined_user_functions:
            raise MnemoCompileError(
                "mnemo_pthread_parallel_with: worker e continuazione devono essere definite nel file"
            )
        if not _pthread_worker_has_no_params(f_work, ctx):
            raise MnemoCompileError(
                "mnemo_pthread_parallel_with: il worker deve essere `void f(void)`"
            )
        if not _pthread_worker_has_no_params(f_cont, ctx):
            raise MnemoCompileError(
                "mnemo_pthread_parallel_with: la continuazione deve essere `void g(void)`"
            )
        chx = _file_scope_channel_actuals(ctx)
        return [
            IPar(
                [
                    [ICall(f_work, _parallel_branch_mem_actuals(ctx, left=False) + chx)],
                    [ICall(f_cont, _parallel_branch_mem_actuals(ctx, left=True) + chx)],
                ]
            )
        ]

    if nm == "mnemo_pthread_parallel_with1":
        if ctx.mem_layout is None:
            raise MnemoCompileError("mnemo_pthread_parallel_with1: layout memoria mancante")
        if len(exprs) != 3:
            raise MnemoCompileError(
                "mnemo_pthread_parallel_with1(void (*w)(T), arg, void (*cont)(void)): "
                "servono 3 argomenti"
            )
        a0, a1, a2 = exprs[0], exprs[1], exprs[2]
        if not isinstance(a0, c.ID) or not isinstance(a2, c.ID):
            raise MnemoCompileError(
                "mnemo_pthread_parallel_with1: worker e continuazione come nomi di funzione"
            )
        f_work, f_cont = a0.name, a2.name
        if f_work not in ctx.defined_user_functions or f_cont not in ctx.defined_user_functions:
            raise MnemoCompileError(
                "mnemo_pthread_parallel_with1: worker e continuazione devono essere definite nel file"
            )
        if not _pthread_worker_has_no_params(f_cont, ctx):
            raise MnemoCompileError(
                "mnemo_pthread_parallel_with1: la continuazione deve essere `void g(void)`"
            )
        pre = _pthread_assign_worker_first_scalar_arg(
            f_work, a1, ctx, mem_partition_index=1
        )
        ctx.use_hist = True
        chx = _file_scope_channel_actuals(ctx)
        return pre + [
            IPar(
                [
                    [ICall(f_work, _parallel_branch_mem_actuals(ctx, left=False) + chx)],
                    [ICall(f_cont, _parallel_branch_mem_actuals(ctx, left=True) + chx)],
                ]
            )
        ]

    if nm == "mnemo_pthread_parallel2":
        if ctx.mem_layout is None:
            raise MnemoCompileError("mnemo_pthread_parallel2: layout memoria mancante")
        if len(exprs) < 2:
            raise MnemoCompileError(
                "mnemo_pthread_parallel2: attesi almeno f e g (nomi di funzione)"
            )
        a0, a1 = exprs[0], exprs[1]
        if not isinstance(a0, c.ID) or not isinstance(a1, c.ID):
            raise MnemoCompileError(
                "mnemo_pthread_parallel2: i primi due argomenti devono essere nomi di funzione"
            )
        f0, f1 = a0.name, a1.name
        if f0 not in ctx.defined_user_functions or f1 not in ctx.defined_user_functions:
            raise MnemoCompileError(
                "mnemo_pthread_parallel2: entrambe le funzioni devono essere definite nel file"
            )
        fdef0 = _get_funcdef(ctx.file_ast, f0)
        fdef1 = _get_funcdef(ctx.file_ast, f1)
        if fdef0 is None or fdef1 is None:
            raise MnemoCompileError("mnemo_pthread_parallel2: definizione funzione mancante")
        fd0 = fdef0.decl.type
        fd1 = fdef1.decl.type
        if not isinstance(fd0, c.FuncDecl) or not isinstance(fd1, c.FuncDecl):
            raise MnemoCompileError("mnemo_pthread_parallel2: firma worker non valida")
        pm0 = _Ctx()
        pm0.typedef_map = dict(ctx.typedef_map)
        pm0.struct_specs = dict(ctx.struct_specs)
        pm0.union_specs = dict(ctx.union_specs)
        pm0.enum_constants = dict(ctx.enum_constants)
        pm0.array_param_names = set()
        pm1 = _Ctx()
        pm1.typedef_map = dict(ctx.typedef_map)
        pm1.struct_specs = dict(ctx.struct_specs)
        pm1.union_specs = dict(ctx.union_specs)
        pm1.enum_constants = dict(ctx.enum_constants)
        pm1.array_param_names = set()
        g0 = _func_param_slot_groups(fd0, ctx.typedef_map, pm0)
        g1 = _func_param_slot_groups(fd1, ctx.typedef_map, pm1)
        expected_len = 2 + len(g0) + len(g1)
        if len(exprs) != expected_len:
            raise MnemoCompileError(
                "mnemo_pthread_parallel2: numero argomenti errato — attesi "
                f"{expected_len} (due nomi di funzione, poi {len(g0)} per `{f0}`, "
                f"{len(g1)} per `{f1}`), ne ho {len(exprs)}"
            )
        raw0 = exprs[2 : 2 + len(g0)]
        raw1 = exprs[2 + len(g0) :]
        pre: list[Instr] = []
        if expected_len > 2:
            pre.extend(_pthread_assign_worker_params(f0, raw0, ctx, mem_partition_index=0))
            pre.extend(_pthread_assign_worker_params(f1, raw1, ctx, mem_partition_index=1))
            ctx.use_hist = True
        chx = _file_scope_channel_actuals(ctx)
        return pre + [
            IPar(
                [
                    [ICall(f0, _parallel_branch_mem_actuals(ctx, left=True) + chx)],
                    [ICall(f1, _parallel_branch_mem_actuals(ctx, left=False) + chx)],
                ]
            )
        ]

    if nm == "pthread_mutex_init":
        if len(exprs) != 2:
            raise MnemoCompileError("pthread_mutex_init: attesi 2 argomenti")
        vn = _pthread_mutex_ptr_name(exprs[0])
        if vn not in ctx.channel_kairos:
            raise MnemoCompileError(f"pthread_mutex_init: {vn!r} non è un pthread_mutex_t")
        ch = ctx.channel_kairos[vn]
        tok = ctx.fresh_temp()
        ctx.use_hist = True
        return [
            IComment("pthread_mutex_init → token su canale (mutex libero)"),
            IConst(tok, 1),
            ISsend(ch, [tok]),
        ]

    if nm == "pthread_mutex_lock":
        if len(exprs) != 1:
            raise MnemoCompileError("pthread_mutex_lock: atteso 1 argomento")
        vn = _pthread_mutex_ptr_name(exprs[0])
        if vn not in ctx.channel_kairos:
            raise MnemoCompileError(f"pthread_mutex_lock: {vn!r} non è un pthread_mutex_t")
        ch = ctx.channel_kairos[vn]
        t = ctx.fresh_temp()
        ctx.use_hist = True
        return [
            IComment("pthread_mutex_lock → srecv token (π-style)"),
            ISrecv([t], ch),
        ]

    if nm == "pthread_mutex_unlock":
        if len(exprs) != 1:
            raise MnemoCompileError("pthread_mutex_unlock: atteso 1 argomento")
        vn = _pthread_mutex_ptr_name(exprs[0])
        if vn not in ctx.channel_kairos:
            raise MnemoCompileError(f"pthread_mutex_unlock: {vn!r} non è un pthread_mutex_t")
        ch = ctx.channel_kairos[vn]
        tok = ctx.fresh_temp()
        ctx.use_hist = True
        return [IConst(tok, 1), ISsend(ch, [tok])]

    if nm == "pthread_mutex_destroy":
        if len(exprs) != 1:
            raise MnemoCompileError("pthread_mutex_destroy: atteso 1 argomento")
        vn = _pthread_mutex_ptr_name(exprs[0])
        if vn not in ctx.channel_kairos:
            raise MnemoCompileError(f"pthread_mutex_destroy: {vn!r} non è un pthread_mutex_t")
        ch = ctx.channel_kairos[vn]
        t = ctx.fresh_temp()
        ctx.use_hist = True
        return [
            IComment("pthread_mutex_destroy: svuota token residuo sul canale (prima del delocal)"),
            ISrecv([t], ch),
        ]

    return None


def _scalar_array_param_name(node: c.Decl, td: dict[str, c.Node]) -> str | None:
    """`int a[10]` come parametro → decay a puntatore (stesso nome)."""
    if not isinstance(node.type, c.ArrayDecl):
        return None
    cur = node.type.type
    while isinstance(cur, c.ArrayDecl):
        cur = cur.type
    if not isinstance(cur, c.TypeDecl) or not isinstance(cur.type, c.IdentifierType):
        return None
    if not _is_scalar_type_names(list(cur.type.names), td):
        return None
    if cur.declname is None:
        return None
    return str(cur.declname)


def _struct_tag_for_decl_type(decl_type: c.Node, ctx: _Ctx) -> str | None:
    cur: c.Node = decl_type
    while isinstance(cur, c.TypeDecl):
        cur = cur.type
    if isinstance(cur, c.Struct):
        if cur.decls:
            return None
        if cur.name and cur.name in ctx.struct_specs:
            return cur.name
        return None
    if isinstance(cur, c.IdentifierType) and len(cur.names) == 1:
        nm = cur.names[0]
        leaf = _follow_typedef_chain([nm], ctx.typedef_map, set())
        if isinstance(leaf, c.Struct):
            if leaf.name and leaf.name in ctx.struct_specs:
                return leaf.name
            if leaf.decls and nm in ctx.struct_specs:
                return nm
    return None


def _union_tag_for_decl_type(decl_type: c.Node, ctx: _Ctx) -> str | None:
    cur: c.Node = decl_type
    while isinstance(cur, c.TypeDecl):
        cur = cur.type
    if isinstance(cur, c.Union):
        if cur.decls:
            return None
        if cur.name and cur.name in ctx.union_specs:
            return cur.name
        return None
    if isinstance(cur, c.IdentifierType) and len(cur.names) == 1:
        nm = cur.names[0]
        leaf = _follow_typedef_chain([nm], ctx.typedef_map, set())
        if isinstance(leaf, c.Union):
            if leaf.name and leaf.name in ctx.union_specs:
                return leaf.name
            if leaf.decls and nm in ctx.union_specs:
                return nm
    return None


def _struct_field_local(var: str, field: str) -> str:
    return f"{var}__{field}"


def _structref_base_and_path(expr: c.StructRef) -> tuple[str, list[str]]:
    """Es. `o.a.b` → (`o`, [`a`,`b`]); supporta `StructRef` annidati nel campo base."""
    parts: list[str] = []
    cur: c.Node = expr
    while isinstance(cur, c.StructRef):
        if cur.type not in (".", "->"):
            raise MnemoCompileError("struct/union: solo `.` o `->`")
        if not isinstance(cur.field, c.ID):
            raise MnemoCompileError("nome campo atteso")
        parts.insert(0, cur.field.name)
        cur = cur.name
    if not isinstance(cur, c.ID):
        raise MnemoCompileError("la base di `.campo` deve essere un identificatore")
    return cur.name, parts


def _field_word_offset(tag: str, mangled: str, ctx: _Ctx) -> int:
    spec = ctx.struct_specs.get(tag)
    if not spec:
        raise MnemoCompileError(f"struct {tag!r}: metadati mancanti")
    off_b = 0
    for fn, fty in spec:
        if fn == mangled:
            return off_b // _SIZEOF_SCALAR
        off_b += _sizeof_of_c_type_node(fty, ctx)
    raise MnemoCompileError(f"struct {tag}: campo {mangled!r} assente")


def _pointee_struct_tag(ptr_type: c.Node, ctx: _Ctx) -> str:
    cur = ptr_type
    if isinstance(cur, c.PtrDecl):
        cur = cur.type
    while isinstance(cur, c.PtrDecl):
        cur = cur.type
    st = _struct_tag_for_decl_type(cur, ctx)
    if st is None:
        raise MnemoCompileError("puntatore a struct atteso per `->`")
    return st


def _enum_scalar_decl_name(node: c.Decl) -> str | None:
    """`enum E x` (enum come tipo intero)."""
    t = node.type
    if isinstance(t, c.TypeDecl) and isinstance(t.type, c.Enum):
        if t.declname is not None:
            return str(t.declname)
    return None


def _int_ptr_var_decl_name(node: c.Decl, td: dict[str, c.Node]) -> str | None:
    """`int *p`, `unsigned *p`, `unsigned int *p` (un solo `*`)."""
    cur = node.type
    if not isinstance(cur, c.PtrDecl):
        return None
    inner = cur.type
    if not isinstance(inner, c.TypeDecl):
        return None
    if not isinstance(inner.type, c.IdentifierType):
        return None
    try:
        ex = _expand_typedef_names(list(inner.type.names), td)
    except MnemoCompileError:
        return None
    if tuple(ex) not in (("int",), ("unsigned", "int"), ("unsigned",)):
        return None
    if inner.declname is None:
        return None
    return str(inner.declname)


def _void_ptr_param_name(node: c.Decl) -> str | None:
    """`void *p` (parametro)."""
    cur = node.type
    if not isinstance(cur, c.PtrDecl):
        return None
    inner = cur.type
    if not isinstance(inner, c.TypeDecl):
        return None
    if not isinstance(inner.type, c.IdentifierType):
        return None
    if inner.type.names != ["void"]:
        return None
    if inner.declname is None:
        return None
    return str(inner.declname)


def _struct_pointer_param_name(node: c.Decl, ctx: _Ctx) -> str | None:
    """`mps_t *p` con `mps_t` typedef di struct — un solo slot (handle / indirizzo)."""
    cur = node.type
    if not isinstance(cur, c.PtrDecl):
        return None
    pointee = cur.type
    st = _struct_tag_for_decl_type(pointee, ctx)
    if st is None:
        return None
    if not isinstance(pointee, c.TypeDecl) or pointee.declname is None:
        return None
    return str(pointee.declname)


def _cast_accepts_pointer_or_scalar(cast_node: c.Cast, td: dict[str, c.Node]) -> bool:
    tt = cast_node.to_type
    if isinstance(tt, c.TypeDecl) and isinstance(tt.type, c.IdentifierType):
        if tt.type.names == ["void"]:
            return True
        return _is_scalar_type_names(tt.type.names, td)
    if isinstance(tt, c.Typename):
        q = tt.type
        if isinstance(q, c.PtrDecl):
            leaf = q
            while isinstance(leaf, c.PtrDecl):
                leaf = leaf.type
            if isinstance(leaf, c.TypeDecl) and isinstance(leaf.type, c.IdentifierType):
                nms = leaf.type.names
                return nms == ["void"] or nms == ["int"] or _is_scalar_type_names(nms, td)
    return False


def _file_ast_needs_ptr_pool(ast: c.FileAST) -> bool:
    def walk(node: object) -> bool:
        if node is None:
            return False
        if isinstance(node, c.Decl) and _int_ptr_var_decl_name(node, {}) is not None:
            return True
        if isinstance(node, c.UnaryOp) and node.op == "*":
            return True
        if isinstance(node, c.FuncCall) and isinstance(node.name, c.ID):
            if node.name.name in ("malloc", "free"):
                return True
        if not hasattr(node, "children"):
            return False
        for _n, ch in node.children():
            if ch is None:
                continue
            if isinstance(ch, list):
                for item in ch:
                    if walk(item):
                        return True
            else:
                if walk(ch):
                    return True
        return False

    for ext in ast.ext:
        if walk(ext):
            return True
    return False


def _register_ptr_pool_locals(ctx: _Ctx) -> None:
    if ctx.mem_layout is not None:
        if _PTR_POOL_CTR not in ctx.int_locals:
            ctx.int_locals.add(_PTR_POOL_CTR)
            ctx.decl_order.append(_PTR_POOL_CTR)
        return
    for n in _ptr_pool_mem_names(ctx) + (_PTR_POOL_CTR,):
        if n not in ctx.int_locals:
            ctx.int_locals.add(n)
            ctx.decl_order.append(n)


def _func_return_is_void(fd: c.FuncDecl) -> bool:
    """`void f(...)` — il tipo di ritorno in pycparser è `fd.type` (TypeDecl o no)."""
    rt = fd.type
    if isinstance(rt, c.TypeDecl) and isinstance(rt.type, c.IdentifierType):
        return rt.type.names == ["void"]
    return False


def _callable_returns_int(fd: c.FuncDecl, td: dict[str, c.Node]) -> bool:
    return _return_is_int_like(fd, td)


def _return_is_int_like(fd: c.FuncDecl, td: dict[str, c.Node]) -> bool:
    """void*, int*, int, struct/union per valore, …"""
    if _func_return_is_void(fd):
        return False
    rt = fd.type
    if isinstance(rt, c.PtrDecl):
        return True
    if isinstance(rt, c.TypeDecl):
        if isinstance(rt.type, c.IdentifierType):
            if _is_scalar_type_names(rt.type.names, td):
                return True
            if len(rt.type.names) == 1 and rt.type.names[0] in td:
                leaf = _follow_typedef_chain(list(rt.type.names), td, set())
                if isinstance(leaf, (c.Struct, c.Union)):
                    return True
            raise MnemoCompileError(f"tipo di ritorno non supportato: {list(rt.type.names)!r}")
        if isinstance(rt.type, (c.Struct, c.Union)):
            return True
    raise MnemoCompileError(f"tipo di ritorno non supportato: {type(rt).__name__}")


def _pointer_level(decl_type: c.Node) -> int:
    """Conta PtrDecl e ArrayDecl come livelli di indirection (ordine arbitrario nel tipo)."""
    n = 0
    cur: c.Node = decl_type
    while isinstance(cur, (c.PtrDecl, c.ArrayDecl)):
        n += 1
        cur = cur.type
    return n


def _type_leaf(decl_type: c.Node) -> tuple[list[str], str | None]:
    """
    Raggiunge TypeDecl / IdentifierType tra PtrDecl e ArrayDecl.
    `char *argv[]` ha spesso ArrayDecl esterno e PtrDecl interno: strippare
    prima tutti i Ptr e poi tutti gli Array fallisce (resta PtrDecl sopra il foglia).
    """
    cur: c.Node = decl_type
    while isinstance(cur, (c.PtrDecl, c.ArrayDecl)):
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


def _func_param_names(fd: c.FuncDecl, td: dict[str, c.Node], ctx: _Ctx) -> list[str]:
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
            n = _scalar_array_param_name(p, td)
            if n is not None:
                ctx.array_param_names.add(n)
            if n is None:
                n = _scalar_decl_name(p, td)
            if n is None:
                n = _enum_scalar_decl_name(p)
            if n is None:
                n = _int_ptr_var_decl_name(p, td)
            if n is None:
                n = _void_ptr_param_name(p)
            if n is None:
                n = _struct_pointer_param_name(p, ctx)
            if n is None:
                raise MnemoCompileError("tipo parametro non supportato")
            names.append(n)
        else:
            raise MnemoCompileError(f"parametro non supportato: {type(p).__name__}")
    return names


def _func_param_storage_names(fd: c.FuncDecl, td: dict[str, c.Node], ctx: _Ctx) -> list[str]:
    """Nomi di slot per parametri (struct appiattiti come variabili struct)."""
    if fd.args is None:
        return []
    out: list[str] = []
    for p in fd.args.params:
        if isinstance(p, c.Typename):
            ty = p.type
            if isinstance(ty, c.TypeDecl) and isinstance(ty.type, c.IdentifierType):
                if ty.type.names == ["void"]:
                    continue
            raise MnemoCompileError("parametro Typename non supportato")
        elif isinstance(p, c.Decl):
            st_tag = _struct_tag_for_decl_type(p.type, ctx)
            if st_tag is not None:
                if not isinstance(p.type, c.TypeDecl) or p.type.declname is None:
                    raise MnemoCompileError("struct: nome parametro mancante")
                varname = str(p.type.declname)
                fields = ctx.struct_specs.get(st_tag)
                if not fields:
                    raise MnemoCompileError(f"struct {st_tag}: definizione mancante")
                for fn, _fty in fields:
                    out.append(_struct_field_local(varname, fn))
                continue
            ut = _union_tag_for_decl_type(p.type, ctx)
            if ut is not None:
                if not isinstance(p.type, c.TypeDecl) or p.type.declname is None:
                    raise MnemoCompileError("union: nome parametro mancante")
                varname = str(p.type.declname)
                if ut not in ctx.union_specs:
                    raise MnemoCompileError(f"union {ut}: definizione mancante")
                out.append(varname)
                continue
            n = _scalar_array_param_name(p, td)
            if n is not None:
                ctx.array_param_names.add(n)
            if n is None:
                n = _scalar_decl_name(p, td)
            if n is None:
                n = _enum_scalar_decl_name(p)
            if n is None:
                n = _int_ptr_var_decl_name(p, td)
            if n is None:
                n = _void_ptr_param_name(p)
            if n is None:
                n = _struct_pointer_param_name(p, ctx)
            if n is None:
                raise MnemoCompileError("tipo parametro non supportato")
            out.append(n)
        else:
            raise MnemoCompileError(f"parametro non supportato: {type(p).__name__}")
    return out


def _func_param_slot_groups(
    fd: c.FuncDecl, td: dict[str, c.Node], ctx: _Ctx
) -> list[list[str]]:
    """Gruppi di slot per ogni parametro formale (struct → più nomi)."""
    if fd.args is None:
        return []
    out: list[list[str]] = []
    for p in fd.args.params:
        if isinstance(p, c.Typename):
            ty = p.type
            if isinstance(ty, c.TypeDecl) and isinstance(ty.type, c.IdentifierType):
                if ty.type.names == ["void"]:
                    continue
            raise MnemoCompileError("parametro Typename non supportato")
        elif isinstance(p, c.Decl):
            st_tag = _struct_tag_for_decl_type(p.type, ctx)
            if st_tag is not None:
                if not isinstance(p.type, c.TypeDecl) or p.type.declname is None:
                    raise MnemoCompileError("struct: nome parametro mancante")
                varname = str(p.type.declname)
                fields = ctx.struct_specs.get(st_tag)
                if not fields:
                    raise MnemoCompileError(f"struct {st_tag}: definizione mancante")
                out.append([_struct_field_local(varname, fn) for fn, _ in fields])
                continue
            ut = _union_tag_for_decl_type(p.type, ctx)
            if ut is not None:
                if not isinstance(p.type, c.TypeDecl) or p.type.declname is None:
                    raise MnemoCompileError("union: nome parametro mancante")
                varname = str(p.type.declname)
                if ut not in ctx.union_specs:
                    raise MnemoCompileError(f"union {ut}: definizione mancante")
                out.append([varname])
                continue
            n = _scalar_array_param_name(p, td)
            if n is not None:
                ctx.array_param_names.add(n)
            if n is None:
                n = _scalar_decl_name(p, td)
            if n is None:
                n = _enum_scalar_decl_name(p)
            if n is None:
                n = _int_ptr_var_decl_name(p, td)
            if n is None:
                n = _void_ptr_param_name(p)
            if n is None:
                n = _struct_pointer_param_name(p, ctx)
            if n is None:
                raise MnemoCompileError("tipo parametro non supportato")
            out.append([n])
        else:
            raise MnemoCompileError(f"parametro non supportato: {type(p).__name__}")
    return out


def _flatten_user_call_arguments(
    raw_exprs: list[c.Node],
    groups: list[list[str]],
    ctx: _Ctx,
    layout: ProgramMemLayout,
) -> tuple[list[Instr], list[c.Node]]:
    """
    Appiattisce argomenti verso gli slot del callee: struct → campi;
    struct da `make()` → chiama il callee interno e usa temporanei per parola.
    """
    leading: list[Instr] = []
    out: list[c.Node] = []
    ei = 0
    for group in groups:
        if ei >= len(raw_exprs):
            raise MnemoCompileError("troppo pochi argomenti nella chiamata")
        ex = raw_exprs[ei]
        ei += 1
        if len(group) == 1:
            out.append(ex)
            continue
        if isinstance(ex, c.FuncCall) and isinstance(ex.name, c.ID):
            inner_n = ex.name.name
            if ctx.file_ast is not None:
                fd_in = _get_funcdef(ctx.file_ast, inner_n)
                if fd_in is not None:
                    rw_in = layout.ret_words.get(inner_n, 0)
                    if rw_in == len(group):
                        sinks = [ctx.fresh_temp() for _ in range(rw_in)]
                        leading.extend(_lower_funccall_with_ret(ex, ctx, sinks))
                        coord = getattr(ex, "coord", None)
                        for s in sinks:
                            out.append(c.ID(s, coord))
                        continue
        if not isinstance(ex, c.ID):
            raise MnemoCompileError(
                "parametro struct: variabile struct o funzione che restituisce "
                "lo stesso numero di parole della struct attesa"
            )
        vn = ex.name
        if vn not in ctx.struct_tag_of_var:
            raise MnemoCompileError(
                f"parametro struct: {vn!r} non è una variabile struct"
            )
        tag = ctx.struct_tag_of_var[vn]
        fields = ctx.struct_specs.get(tag)
        if not fields or len(fields) != len(group):
            raise MnemoCompileError(
                "passaggio struct per valore: tipo incompatibile con la firma"
            )
        coord = getattr(ex, "coord", None)
        for fname, _fty in fields:
            out.append(c.ID(_struct_field_local(vn, fname), coord))
    if ei != len(raw_exprs):
        raise MnemoCompileError("troppi argomenti nella chiamata")
    return leading, out


def _merge_proc_returns_int(
    ast: c.FileAST, td: dict[str, c.Node]
) -> dict[str, bool]:
    sig: dict[str, bool] = {n: False for n in BUILTIN_KAIROS_PROCS}
    for ext in ast.ext:
        if isinstance(ext, c.Decl) and isinstance(ext.type, c.FuncDecl):
            n = ext.name
            if not n or n == "main":
                continue
            sig[n] = _return_is_int_like(ext.type, td)
    for ext in ast.ext:
        if isinstance(ext, c.FuncDef):
            n = ext.decl.name
            if n == "main":
                continue
            fd = ext.decl.type
            if isinstance(fd, c.FuncDecl):
                sig[n] = _return_is_int_like(fd, td)
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


def _sizeof_struct_tag(tag: str, ctx: _Ctx) -> int:
    fields = ctx.struct_specs.get(tag)
    if not fields:
        raise MnemoCompileError(
            f"sizeof(struct …): tag {tag!r} sconosciuto o definizione mancante"
        )
    total = 0
    for _fn, fty in fields:
        total += _sizeof_of_c_type_node(fty, ctx)
    return total


def _sizeof_union_tag(tag: str, ctx: _Ctx) -> int:
    fields = ctx.union_specs.get(tag)
    if not fields:
        raise MnemoCompileError(
            f"sizeof(union …): tag {tag!r} sconosciuto o definizione mancante"
        )
    return max(_sizeof_of_c_type_node(fty, ctx) for _fn, fty in fields)


def _sizeof_of_c_type_node(node: c.Node, ctx: _Ctx) -> int:
    """
    `sizeof` risolto staticamente: `Decl.type`, `Typename.type`, o equivalente.
    Puntatori → _SIZEOF_POINTER; scalari Mnemo → _SIZEOF_SCALAR; char → 1; struct somma campi.
    """
    if isinstance(node, c.Typename):
        node = node.type
    if isinstance(node, c.PtrDecl):
        return _SIZEOF_POINTER
    if isinstance(node, c.ArrayDecl):
        n = _array_dim_const(node.dim)
        return n * _sizeof_of_c_type_node(node.type, ctx)
    if isinstance(node, c.TypeDecl):
        if isinstance(node.type, c.IdentifierType):
            names = list(node.type.names)
            if len(names) == 1:
                nm = names[0]
                if nm in ctx.typedef_map:
                    leaf = _follow_typedef_chain([nm], ctx.typedef_map, set())
                    if isinstance(leaf, c.Struct):
                        tag = leaf.name if leaf.name else nm
                        return _sizeof_struct_tag(tag, ctx)
                    if isinstance(leaf, c.Union):
                        tag = leaf.name if leaf.name else nm
                        return _sizeof_union_tag(tag, ctx)
            try:
                ex = _expand_typedef_names(names, ctx.typedef_map)
            except MnemoCompileError as e:
                raise MnemoCompileError(f"sizeof: tipo non supportato: {names!r}") from e
            if ex in (["char"], ["unsigned", "char"]):
                return _SIZEOF_CHAR
            if ex == ["void"]:
                raise MnemoCompileError("sizeof(void) non valido")
            if tuple(ex) in _SCALAR_NAMES:
                return _SIZEOF_SCALAR
            raise MnemoCompileError(f"sizeof: tipo non supportato: {ex!r}")
        if isinstance(node.type, c.Struct):
            st = node.type
            if st.decls:
                raise MnemoCompileError(
                    "sizeof: usa `sizeof(struct Tag)` con tag già definito, non una definizione inline"
                )
            tag = st.name
            if tag is None:
                raise MnemoCompileError("sizeof(struct …): tag mancante")
            return _sizeof_struct_tag(tag, ctx)
        if isinstance(node.type, c.Enum):
            return _SIZEOF_SCALAR
        if isinstance(node.type, c.Union):
            un = node.type
            if un.decls:
                raise MnemoCompileError(
                    "sizeof: usa `sizeof(union Tag)` con tag già definito"
                )
            tag = un.name
            if tag is None:
                raise MnemoCompileError("sizeof(union …): tag mancante")
            return _sizeof_union_tag(tag, ctx)
    raise MnemoCompileError(f"sizeof: tipo AST non supportato: {type(node).__name__}")


def _register_param_var_types(ctx: _Ctx, fd: c.FuncDecl) -> None:
    if fd.args is None:
        return
    td = ctx.typedef_map
    for p in fd.args.params:
        if isinstance(p, c.Decl):
            n = _scalar_decl_name(p, td)
            if n is None:
                n = _enum_scalar_decl_name(p)
            if n is None:
                n = _int_ptr_var_decl_name(p, td)
            if n is None:
                n = _void_ptr_param_name(p)
            if n is None:
                n = _struct_pointer_param_name(p, ctx)
            if n:
                if n in ctx.array_param_names:
                    cur = p.type
                    while isinstance(cur, c.ArrayDecl):
                        cur = cur.type
                    ctx.var_types[n] = c.PtrDecl(
                        [],
                        cur,
                        getattr(p.type, "coord", None),
                    )
                else:
                    ctx.var_types[n] = p.type


def _eval_expr_into_var(expr: c.Node, ctx: _Ctx, target: str) -> list[Instr]:
    """Somma il valore di expr su `target` (target parte da 0)."""
    ei, op, tm = _eval_expr(expr, ctx)
    ctx.use_hist = True
    ins = ei + [IHistPush(ctx.hist, target), IAddEq(target, op)]
    post = [IHistPush(ctx.scratch, x) for x in reversed(tm)]
    if tm:
        ctx.use_scratch = True
    return ins + post


def _eval_expr(expr: c.Node, ctx: _Ctx) -> tuple[list[Instr], Var | Imm, list[str]]:
    if isinstance(expr, c.Constant):
        return [], Imm(_const_int(expr)), []

    if isinstance(expr, c.ID):
        if expr.name in ctx.struct_tag_of_var:
            raise MnemoCompileError(
                f"{expr.name!r} è una struct: usa {expr.name}.campo"
            )
        if expr.name in ctx.union_tag_of_var:
            raise MnemoCompileError(
                f"{expr.name!r} è una union: usa {expr.name}.campo"
            )
        if expr.name in ctx.array_info:
            raise MnemoCompileError(
                f"l'array {expr.name!r} non è un valore scalare: usa {expr.name}[…]"
            )
        if expr.name in ctx.int_locals:
            return [], Var(_phys(ctx, expr.name)), []
        if expr.name in ctx.enum_constants:
            return [], Imm(ctx.enum_constants[expr.name]), []
        raise MnemoCompileError(f"identificatore non dichiarato: {expr.name!r}")

    if isinstance(expr, c.StructRef):
        if expr.type == "->":
            if not isinstance(expr.name, c.ID) or not isinstance(expr.field, c.ID):
                raise MnemoCompileError("`->`: sintassi non supportata")
            p = expr.name.name
            if p not in ctx.int_locals:
                raise MnemoCompileError(f"puntatore non dichiarato: {p!r}")
            pty = ctx.var_types.get(p)
            if pty is None:
                raise MnemoCompileError(f"`{p}`: tipo mancante per ->")
            tag = _pointee_struct_tag(pty, ctx)
            mangled = str(expr.field.name)
            spec = ctx.struct_specs.get(tag)
            if not spec or mangled not in [fn for fn, _ in spec]:
                raise MnemoCompileError(f"struct {tag}: campo {mangled!r} assente")
            off_w = _field_word_offset(tag, mangled, ctx)
            _register_ptr_pool_locals(ctx)
            ei, op, tm = _eval_expr(c.ID(p, expr.coord), ctx)
            t_slot = ctx.fresh_temp()
            t_out = ctx.fresh_temp()
            ctx.use_hist = True
            rop: Operand = op if isinstance(op, Imm) else Var(op.name)
            pre = (
                ei
                + [IHistPush(ctx.hist, t_slot), IAddEq(t_slot, rop)]
                + ([IAddEq(t_slot, Imm(off_w))] if off_w != 0 else [])
            )
            ins = pre + [
                ICall(
                    "__mn_pool_load",
                    [t_slot] + list(_ptr_pool_mem_names(ctx)) + [t_out],
                )
            ]
            return ins, Var(t_out), tm + [t_slot, t_out]
        base, path = _structref_base_and_path(expr)
        mangled = "__".join(path)
        if base in ctx.union_tag_of_var:
            if len(path) != 1:
                raise MnemoCompileError("union: un solo livello di campo")
            field = path[0]
            tag = ctx.union_tag_of_var[base]
            spec = ctx.union_specs.get(tag)
            if not spec:
                raise MnemoCompileError(f"union {tag!r}: metadati mancanti")
            fnames = [fn for fn, _ in spec]
            if field not in fnames:
                raise MnemoCompileError(f"union {tag}: membro {field!r} assente")
            if base not in ctx.int_locals:
                raise MnemoCompileError(f"union {base!r}: storage mancante")
            return [], Var(_phys(ctx, base)), []
        if base not in ctx.struct_tag_of_var:
            raise MnemoCompileError(f"{base!r} non è una variabile struct")
        tag = ctx.struct_tag_of_var[base]
        spec = ctx.struct_specs.get(tag)
        if not spec:
            raise MnemoCompileError(f"struct {tag!r}: metadati mancanti")
        field_names = [fn for fn, _ in spec]
        if mangled not in field_names:
            raise MnemoCompileError(f"struct {tag}: campo {mangled!r} assente")
        cell = _struct_field_local(base, mangled)
        if cell not in ctx.int_locals:
            raise MnemoCompileError(f"campo struct interno mancante: {cell!r}")
        return [], Var(_phys(ctx, cell)), []

    if isinstance(expr, c.ArrayRef):
        base, subs = _flatten_array_ref_chain(expr)
        if base not in ctx.array_info:
            raise MnemoCompileError(
                f"{base!r} non è un array dichiarato (es. int {base}[N] o int {base}[R][C])"
            )
        info = ctx.array_info[base]
        if len(subs) != len(info.dims):
            raise MnemoCompileError(
                f"array {base!r}: servono {len(info.dims)} indici, ne ho {len(subs)}"
            )
        coord = getattr(expr, "coord", None)
        if all(isinstance(s, c.Constant) for s in subs):
            lin = _const_row_major_linear(subs, info.dims)
            return [], Var(_phys(ctx, _array_elem_local(base, lin))), []
        idx_expr = _c_row_major_index_ast(subs, info.dims, coord)
        pre_l, op_ix, tm_l = _eval_expr(idx_expr, ctx)
        if isinstance(op_ix, Imm):
            tix = ctx.fresh_temp()
            pre_l = pre_l + [IConst(tix, op_ix.value)]
            ix = tix
            tm_l = tm_l + [tix]
        else:
            ix = op_ix.name
        t_dest = ctx.fresh_temp()
        ctx.use_hist = True
        bodies = [
            [
                IHistPush(ctx.hist, t_dest),
                IAddEq(t_dest, Var(_phys(ctx, _array_elem_local(base, kk)))),
            ]
            for kk in range(info.total)
        ]
        chain = _disj_eq_chain(ix, list(range(info.total)), bodies)
        return pre_l + chain, Var(t_dest), tm_l + [t_dest]

    if isinstance(expr, c.TernaryOp):
        out = ctx.fresh_temp()
        then_i = _eval_expr_into_var(expr.iftrue, ctx, out)
        else_i = _eval_expr_into_var(expr.iffalse, ctx, out)
        chain = _lower_if_from_expr(expr.cond, then_i, else_i, ctx)
        return chain, Var(out), [out]

    if isinstance(expr, c.UnaryOp):
        if expr.op == "-":
            inner = expr.expr
            if isinstance(inner, c.Constant):
                return [], Imm(-_const_int(inner)), []
            i0, op0, t0 = _eval_expr(inner, ctx)
            t = ctx.fresh_temp()
            ins = i0 + [ISubEq(t, op0)]
            return ins, Var(t), t0 + [t]
        if expr.op == "sizeof":
            inner = expr.expr
            if isinstance(inner, c.Typename):
                return [], Imm(_sizeof_of_c_type_node(inner, ctx)), []
            if isinstance(inner, c.ID):
                if inner.name in ctx.struct_tag_of_var:
                    tag = ctx.struct_tag_of_var[inner.name]
                    return [], Imm(_sizeof_struct_tag(tag, ctx)), []
                if inner.name in ctx.union_tag_of_var:
                    tag = ctx.union_tag_of_var[inner.name]
                    return [], Imm(_sizeof_union_tag(tag, ctx)), []
                if inner.name in ctx.array_info:
                    info = ctx.array_info[inner.name]
                    return [], Imm(info.total * info.elem_size), []
                if inner.name in ctx.array_param_names:
                    return [], Imm(_SIZEOF_POINTER), []
                if inner.name not in ctx.var_types:
                    raise MnemoCompileError(
                        f"sizeof({inner.name}): serve un tipo in (…) o una variabile già dichiarata"
                    )
                return [], Imm(_sizeof_of_c_type_node(ctx.var_types[inner.name], ctx)), []
            raise MnemoCompileError(
                "sizeof: supportati solo `sizeof (tipo)` e `sizeof nome_variabile`"
            )
        if expr.op == "&":
            inner = expr.expr
            if isinstance(inner, c.ID):
                n = inner.name
                if n in ctx.slot_index:
                    return [], Imm(ctx.slot_index[n]), []
                if n in ctx.struct_tag_of_var:
                    tag = ctx.struct_tag_of_var[n]
                    fields = ctx.struct_specs.get(tag)
                    if not fields:
                        raise MnemoCompileError(f"struct {tag!r}: metadati mancanti")
                    first = fields[0][0]
                    cell = _struct_field_local(n, first)
                    if cell not in ctx.slot_index:
                        raise MnemoCompileError(
                            f"&{n}: indirizzo (primo campo) non disponibile"
                        )
                    return [], Imm(ctx.slot_index[cell]), []
                raise MnemoCompileError(f"&{n}: indirizzo non disponibile")
            if isinstance(inner, c.StructRef) and inner.type == ".":
                base, path = _structref_base_and_path(inner)
                mangled = "__".join(path)
                if base not in ctx.struct_tag_of_var:
                    raise MnemoCompileError(
                        f"&.{mangled!r}: base non è una variabile struct"
                    )
                cell = _struct_field_local(base, mangled)
                if cell not in ctx.slot_index:
                    raise MnemoCompileError(
                        f"&{base}.{mangled}: indirizzo slot non disponibile"
                    )
                return [], Imm(ctx.slot_index[cell]), []
            raise MnemoCompileError(
                "&: supportati `&x` e `&struct.campo` (punto, catena di campi)"
            )
        if expr.op == "*":
            inner = expr.expr
            _register_ptr_pool_locals(ctx)
            ei_p, op_p, tm_p = _eval_expr(inner, ctx)
            if isinstance(op_p, Imm):
                tmp = ctx.fresh_temp()
                ei_p = ei_p + [IConst(tmp, op_p.value)]
                ptrn = tmp
                tm_p = tm_p + [tmp]
            elif isinstance(op_p, Var):
                ptrn = op_p.name
            else:
                raise MnemoCompileError("dereference: espressione puntatore non valida")
            if ptrn not in ctx.int_locals:
                raise MnemoCompileError("dereference: operando non dichiarato")
            t = ctx.fresh_temp()
            pre_sl, slot_a, tm_sl = _pool_call_slot_arg(ctx, ptrn)
            ins = (
                ei_p
                + pre_sl
                + [
                    ICall(
                        "__mn_pool_load",
                        [slot_a] + list(_ptr_pool_mem_names(ctx)) + [t],
                    )
                ]
            )
            return ins, Var(t), tm_p + tm_sl + [t]
        raise MnemoCompileError(f"operatore unario non supportato: {expr.op!r}")

    if isinstance(expr, c.BinaryOp):
        if expr.op == ",":
            i1, o1, tm1 = _eval_expr(expr.left, ctx)
            ctx.use_hist = True
            discard = list(i1)
            fin = list(tm1)
            if isinstance(o1, Imm):
                if i1 or fin:
                    tx = ctx.fresh_temp()
                    discard.append(IConst(tx, o1.value))
                    fin.append(tx)
            elif not isinstance(o1, Var):
                raise MnemoCompileError("operatore `,`: lhs non valido")
            discard.extend([IHistPush(ctx.scratch, x) for x in reversed(fin)])
            if fin:
                ctx.use_scratch = True
            i2, o2, tm2 = _eval_expr(expr.right, ctx)
            return discard + i2, o2, tm2
        if expr.op == "^":
            i1, o1, tm1 = _eval_expr(expr.left, ctx)
            i2, o2, tm2 = _eval_expr(expr.right, ctx)
            t = ctx.fresh_temp()
            ctx.use_hist = True
            ins = i1 + i2 + [IHistPush(ctx.hist, t), IAddEq(t, o1), IXorEq(t, o2)]
            post = [IHistPush(ctx.scratch, x) for x in reversed(tm1 + tm2)]
            if tm1 or tm2:
                ctx.use_scratch = True
            return ins + post, Var(t), tm1 + tm2 + [t]
        if expr.op in ("+", "-"):
            # Due chiamate `f(...)+g(...)` condividono le celle __mn_mem*: la prima call
            # altera i parametri (es. `n` in mem0); senza ripristino, la seconda usa valori
            # sbagliati (es. `fib(n-1)+fib(n-2)` → il secondo argomento legge `n` già corrotto).
            if (
                isinstance(expr.left, c.FuncCall)
                and isinstance(expr.right, c.FuncCall)
                and ctx.param_storage_order
            ):
                ctx.use_hist = True
                pre_sn: list[Instr] = []
                snap_pairs: list[tuple[str, str]] = []
                for pname in ctx.param_storage_order:
                    if pname not in ctx.int_locals:
                        continue
                    tmp = ctx.fresh_temp()
                    snap_pairs.append((pname, tmp))
                    pre_sn.extend(_lower_assign(tmp, c.ID(pname), ctx))
                i1, o1, tm1 = _eval_expr(expr.left, ctx)
                restore: list[Instr] = []
                for pname, tmp in snap_pairs:
                    phy = _phys(ctx, pname)
                    restore.extend(
                        [IHistPush(ctx.hist, phy), IAddEq(phy, Var(tmp))]
                    )
                i2, o2, tm2 = _eval_expr(expr.right, ctx)
                t = ctx.fresh_temp()
                if expr.op == "+":
                    mid = i1 + restore + i2 + [IAddEq(t, o1), IAddEq(t, o2)]
                else:
                    mid = i1 + restore + i2 + [IAddEq(t, o1), ISubEq(t, o2)]
                ins = pre_sn + mid
                snap_tmps = [tmp for _p, tmp in snap_pairs]
                all_tm = tm1 + tm2 + snap_tmps + [t]
                if tm1 or tm2 or snap_tmps:
                    ctx.use_scratch = True
                # Come il ramo `+` generico: niente push su scratch qui — i chiamanti
                # (_lower_return, _eval_expr_into_var, assegnazioni…) appendono IHistPush
                # dopo aver consumato `op`. Se `post` fosse in `ei`, push(__mn_e5, scratch)
                # azzererebbe il temp prima di mem1 += e5 (es. return fib(n-1)+fib(n-2)).
                return ins, Var(t), all_tm
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
        if _cast_accepts_pointer_or_scalar(expr, ctx.typedef_map):
            return _eval_expr(expr.expr, ctx)
        raise MnemoCompileError("cast non supportato")

    if isinstance(expr, c.ExprList):
        return _eval_expr(_fold_exprlist_as_comma_chain(expr), ctx)

    if isinstance(expr, c.FuncCall):
        if not isinstance(expr.name, c.ID):
            raise MnemoCompileError("callee non è un identificatore")
        name = expr.name.name
        if name == "malloc":
            if name not in ctx.extern_procs:
                raise MnemoCompileError(
                    "malloc: dichiarare es. `void *malloc(int n);` o `void *malloc(unsigned n);`"
                )
            if not ctx.proc_returns_int.get(name, False):
                raise MnemoCompileError("malloc deve restituire un puntatore (void* / int*)")
            _register_ptr_pool_locals(ctx)
            t = ctx.fresh_temp()
            ins = [ICall("__mn_pool_alloc", [_PTR_POOL_CTR, t])]
            return ins, Var(t), [t]
        if name not in ctx.extern_procs:
            raise MnemoCompileError(
                f"chiamata a {name!r}: dichiarare la funzione (prototipo o definizione)"
            )
        if not ctx.proc_returns_int.get(name, False):
            raise MnemoCompileError(
                f"{name} è void: non usabile come sotto-espressione (usa solo come istruzione)"
            )
        if (
            ctx.mem_layout is not None
            and ctx.file_ast is not None
            and _get_funcdef(ctx.file_ast, name) is not None
        ):
            rw_fn = ctx.mem_layout.ret_words.get(name, 0)
            if rw_fn > 1:
                raise MnemoCompileError(
                    f"{name}: ritorno su più parole non usabile come sotto-espressione "
                    f"(usa `struct V v = {name}(…);`)"
                )
        t = ctx.fresh_temp()
        ins = _lower_funccall_with_ret(expr, ctx, t)
        return ins, Var(t), [t]

    raise MnemoCompileError(f"espressione AST non supportata: {type(expr).__name__}")


def _eval_index_to_var(
    expr: c.Node, ctx: _Ctx
) -> tuple[list[Instr], str, list[str]]:
    """Indice array: risultato sempre in una variabile (per confronti if)."""
    i0, op, tm = _eval_expr(expr, ctx)
    if isinstance(op, Imm):
        t = ctx.fresh_temp()
        return i0 + [IConst(t, op.value)], t, tm + [t]
    return i0, op.name, tm


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


def _bind_ctx_layout(ctx: _Ctx, layout: ProgramMemLayout, fn_name: str) -> None:
    ctx.mem_layout = layout
    ctx.fn_name = fn_name
    ctx.total_mem_cells = layout.total_cells
    ctx.heap_base = layout.heap_base
    ctx.proc_ret_words = dict(layout.ret_words)
    ctx.mem_phys.clear()
    ctx.slot_index.clear()
    for (f, log), idx in layout.slot_of.items():
        if f != fn_name:
            continue
        nm = f"__mn_mem{idx}"
        ctx.mem_phys[log] = nm
        ctx.slot_index[log] = idx
    rw = layout.ret_words.get(fn_name, 0)
    if rw == 1:
        rv = ctx.mem_phys.get(MN_RET)
        ctx.ret_vars = [rv] if rv is not None else [MN_RET]
        ctx.ret_var = ctx.ret_vars[0]
    elif rw > 1:
        ctx.ret_vars = [
            ctx.mem_phys[f"__mn_ret{i}"] for i in range(rw)
        ]
        ctx.ret_var = ctx.ret_vars[0]
    else:
        ctx.ret_vars = []
        ctx.ret_var = None


def _get_funcdef(ast: c.FileAST, fn: str) -> c.FuncDef | None:
    for ext in ast.ext:
        if isinstance(ext, c.FuncDef) and ext.decl.name == fn:
            return ext
    return None


def _prepare_call_arg(
    expr: c.Node, ctx: _Ctx
) -> tuple[list[Instr], str, list[str]]:
    if isinstance(expr, c.ID):
        if expr.name in ctx.struct_tag_of_var:
            raise MnemoCompileError(
                f"passaggio struct {expr.name!r} non supportato (usa un campo scalare)"
            )
        if expr.name in ctx.union_tag_of_var:
            raise MnemoCompileError(
                f"passaggio union {expr.name!r} non supportato (usa un membro scalare)"
            )
        if expr.name in ctx.array_info:
            raise MnemoCompileError(
                f"passaggio array {expr.name!r} non supportato (usa puntatore o elemento)"
            )
        if expr.name not in ctx.int_locals:
            raise MnemoCompileError(f"argomento non dichiarato: {expr.name}")
        return [], _phys(ctx, expr.name), []
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
    node: c.FuncCall, ctx: _Ctx, ret_sink: str | list[str] | None
) -> list[Instr]:
    if not isinstance(node.name, c.ID):
        raise MnemoCompileError("callee non è un identificatore")
    name = node.name.name
    if name not in ctx.extern_procs:
        raise MnemoCompileError(
            f"chiamata a {name!r}: dichiarare la funzione (prototipo o definizione)"
        )
    wants = ctx.proc_returns_int.get(name, False)
    el = node.args
    exprs = list(el.exprs) if el is not None else []

    if ctx.mem_layout is not None and ctx.file_ast is not None:
        fd_u = _get_funcdef(ctx.file_ast, name)
        if fd_u is not None:
            callee_fd = fd_u.decl.type
            if not isinstance(callee_fd, c.FuncDecl):
                raise MnemoCompileError("chiamata: callee malformato")
            layout = ctx.mem_layout
            callee_mini = _Ctx()
            callee_mini.typedef_map = ctx.typedef_map
            callee_mini.struct_specs = ctx.struct_specs
            callee_mini.union_specs = ctx.union_specs
            callee_mini.enum_constants = ctx.enum_constants
            callee_mini.array_param_names = set()
            param_logs = _func_param_storage_names(
                callee_fd, ctx.typedef_map, callee_mini
            )
            groups = _func_param_slot_groups(
                callee_fd, ctx.typedef_map, callee_mini
            )
            lead_arg, exprs = _flatten_user_call_arguments(
                exprs, groups, ctx, layout
            )
            rw_c = layout.ret_words.get(name, 0)
            slot_logs = param_logs + _ret_slot_names(rw_c)
            coord = getattr(node, "coord", None)
            if len(exprs) == len(param_logs) and rw_c >= 1:
                for _ in _ret_slot_names(rw_c):
                    exprs.append(c.Constant("int", "0"))
            if len(exprs) != len(slot_logs):
                raise MnemoCompileError(
                    f"{name}: servono {len(slot_logs)} argomenti, ne ho {len(exprs)}"
                )
            pre_uc: list[Instr] = []
            pre_uc.extend(lead_arg)
            for ex, log_key in zip(exprs, slot_logs):
                idx = layout.slot_of[(name, log_key)]
                dst = f"__mn_mem{idx}"
                pre_uc.extend(_lower_assign(dst, ex, ctx))
            mem_args = [f"__mn_mem{i}" for i in range(layout.total_cells)]
            post_uc: list[Instr] = []
            if wants and ret_sink is not None:
                rnames = _ret_slot_names(rw_c)
                if rw_c < 1:
                    pass
                elif isinstance(ret_sink, str):
                    if rw_c != 1:
                        raise MnemoCompileError(
                            f"{name}: ritorno di {rw_c} parole: usare "
                            f"`struct s = {name}(…);` o `return {name}(…)`"
                        )
                    ri = layout.slot_of[(name, rnames[0])]
                    rphys = f"__mn_mem{ri}"
                    post_uc.extend(
                        _lower_assign(ret_sink, c.ID(rphys, coord), ctx)
                    )
                else:
                    if len(ret_sink) != rw_c:
                        raise MnemoCompileError(
                            f"{name}: servono {rw_c} slot di ritorno, "
                            f"ne ho {len(ret_sink)}"
                        )
                    for dst, rn in zip(ret_sink, rnames):
                        ri = layout.slot_of[(name, rn)]
                        rphys = f"__mn_mem{ri}"
                        post_uc.extend(
                            _lower_assign(dst, c.ID(rphys, coord), ctx)
                        )
            ctx.use_hist = True
            chx = _file_scope_channel_actuals(ctx)
            return pre_uc + [ICall(name, mem_args + chx)] + post_uc

    if wants and ret_sink is None:
        raise MnemoCompileError(f"{name} restituisce un valore: uso interno errato")
    if not wants and ret_sink is not None:
        raise MnemoCompileError(f"{name} è void: non richiede slot di ritorno")

    pre: list[Instr] = []
    arg_names: list[str] = []
    to_clear: list[str] = []
    for ex in exprs:
        pi, an, tc = _prepare_call_arg(ex, ctx)
        pre.extend(pi)
        arg_names.append(an)
        to_clear.extend(tc)
    if name == "free":
        _register_ptr_pool_locals(ctx)
        if len(arg_names) != 1:
            raise MnemoCompileError("free richiede un argomento (puntatore)")
        if to_clear:
            ctx.use_scratch = True
        post = [IHistPush(ctx.scratch, t) for t in reversed(to_clear)]
        ptr_phys = arg_names[0]
        pre_al, free_slot, tm_al = _pool_call_slot_arg(ctx, ptr_phys)
        if tm_al:
            ctx.use_scratch = True
        post_al = [IHistPush(ctx.scratch, t) for t in reversed(tm_al)]
        return pre + pre_al + [
            ICall(
                "__mn_pool_free",
                [free_slot] + list(_ptr_pool_mem_names(ctx)) + [_PTR_POOL_CTR],
            )
        ] + post + post_al
    if wants:
        if ret_sink is None or not isinstance(ret_sink, str):
            raise MnemoCompileError(
                f"{name} restituisce un valore: uso interno errato (sink)"
            )
        arg_names.append(ret_sink)
    if to_clear:
        ctx.use_scratch = True
    post = [IHistPush(ctx.scratch, t) for t in reversed(to_clear)]
    return pre + [ICall(name, arg_names)] + post


def _lower_return_aggregate(expr: c.Node, ctx: _Ctx) -> list[Instr]:
    """return con tipo struct su più parole (__mn_ret0, …)."""
    rw = len(ctx.ret_vars)
    if rw < 2:
        raise MnemoCompileError("return aggregato: errore interno")
    if isinstance(expr, c.FuncCall):
        if not isinstance(expr.name, c.ID):
            raise MnemoCompileError("return: callee non valido")
        callee = expr.name.name
        if ctx.file_ast is None or ctx.mem_layout is None:
            raise MnemoCompileError("return f(): contesto senza layout")
        fd_u = _get_funcdef(ctx.file_ast, callee)
        if fd_u is None:
            raise MnemoCompileError(
                "return f() su più parole: solo funzioni definite nello stesso file"
            )
        rw_c = ctx.mem_layout.ret_words.get(callee, 0)
        if rw_c != rw:
            raise MnemoCompileError(
                "return f(): tipo di ritorno incompatibile con la funzione corrente"
            )
        return _lower_funccall_with_ret(expr, ctx, list(ctx.ret_vars)) + [IReturn()]
    if isinstance(expr, c.ID):
        vn = expr.name
        if vn not in ctx.struct_tag_of_var:
            raise MnemoCompileError(
                "return su più parole: serve una variabile struct o una chiamata"
            )
        tag = ctx.struct_tag_of_var[vn]
        fields = ctx.struct_specs.get(tag)
        if not fields or len(fields) != rw:
            raise MnemoCompileError(
                "return struct: campi incompatibili con il tipo di ritorno "
                "(struct packed / annidate non allineate)"
            )
        coord = getattr(expr, "coord", None)
        out: list[Instr] = []
        for (fname, _), rv in zip(fields, ctx.ret_vars):
            src = _struct_field_local(vn, fname)
            ei, op, temps = _eval_expr(c.ID(src, coord), ctx)
            ctx.use_hist = True
            if temps:
                ctx.use_scratch = True
            out.extend(ei + [IHistPush(ctx.hist, rv), IAddEq(rv, op)])
            for tmp in reversed(temps):
                out.append(IHistPush(ctx.scratch, tmp))
        out.append(IReturn())
        return out
    raise MnemoCompileError(
        "return aggregato: usa una variabile struct o `return f()`"
    )


def _loop_body_continue_is_noop(stmt: c.Node | None) -> bool:
    """
    Corpo che è solo `continue` (eventualmente in `{}` con vuoti) non fa nulla:
    salta solo la «coda» del blocco, che qui non esiste → come `{}`.
    In quel caso non serve ct_var / ILocalBlock per continue.
    """
    if stmt is None:
        return True
    if isinstance(stmt, (c.Continue, c.EmptyStatement)):
        return True
    if isinstance(stmt, c.Compound):
        items = [
            x
            for x in (stmt.block_items or [])
            if not isinstance(x, c.EmptyStatement)
        ]
        if not items:
            return True
        return len(items) == 1 and _loop_body_continue_is_noop(items[0])
    return False


def _lower_discard_expr_result(expr: c.Node, ctx: _Ctx) -> list[Instr]:
    """Valuta un'espressione e annulla il risultato (es. `(void)x;` o `(int)f();`)."""
    ei, op, temps = _eval_expr(expr, ctx)
    ctx.use_hist = True
    out = list(ei)
    fin = list(temps)
    if isinstance(op, Imm):
        if not ei and not fin:
            return []
        t = ctx.fresh_temp()
        out.append(IConst(t, op.value))
        fin.append(t)
    elif isinstance(op, Var):
        pass
    else:
        raise MnemoCompileError("espressione: risultato non valido")
    if fin:
        ctx.use_scratch = True
        out.extend([IHistPush(ctx.scratch, x) for x in reversed(fin)])
    return out


def _lower_expr_as_stmt(expr: c.Node, ctx: _Ctx) -> list[Instr]:
    if isinstance(expr, c.Assignment):
        return _lower_stmt(expr, ctx)
    if isinstance(expr, c.Cast):
        return _lower_discard_expr_result(expr.expr, ctx)
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
        return _lower_assign(_phys(ctx, v), rhs, ctx)
    raise MnemoCompileError(
        f"espressione non ammessa come istruzione: {type(expr).__name__}"
    )


def _lower_deref_assign(p_name: str, rhs: c.Node, ctx: _Ctx) -> list[Instr]:
    """`*p = rhs` tramite __mn_pool_store (`p` è un identificatore puntatore)."""
    return _lower_deref_assign_phys(_phys(ctx, p_name), rhs, ctx)


def _lower_struct_arrow_assign(lhs: c.StructRef, rhs: c.Node, ctx: _Ctx) -> list[Instr]:
    """`p->campo = rhs` tramite pool store con offset campo (come lettura `->` in _eval_expr)."""
    if lhs.type != "->":
        raise MnemoCompileError("solo `->`")
    if not isinstance(lhs.name, c.ID) or not isinstance(lhs.field, c.ID):
        raise MnemoCompileError("`->`: sintassi non supportata")
    p = lhs.name.name
    if p not in ctx.int_locals:
        raise MnemoCompileError(f"puntatore non dichiarato: {p!r}")
    pty = ctx.var_types.get(p)
    if pty is None:
        raise MnemoCompileError(f"`{p}`: tipo mancante per ->")
    tag = _pointee_struct_tag(pty, ctx)
    mangled = str(lhs.field.name)
    spec = ctx.struct_specs.get(tag)
    if not spec or mangled not in [fn for fn, _ in spec]:
        raise MnemoCompileError(f"struct {tag}: campo {mangled!r} assente")
    off_w = _field_word_offset(tag, mangled, ctx)
    _register_ptr_pool_locals(ctx)
    ei_m, op_m, tm_m = _eval_expr(c.ID(p, lhs.coord), ctx)
    t_slot = ctx.fresh_temp()
    ctx.use_hist = True
    rop: Operand = op_m if isinstance(op_m, Imm) else Var(op_m.name)
    pre_m = (
        ei_m
        + [IHistPush(ctx.hist, t_slot), IAddEq(t_slot, rop)]
        + ([IAddEq(t_slot, Imm(off_w))] if off_w != 0 else [])
    )
    ei_r, op_r, tm_r = _eval_expr(rhs, ctx)
    if isinstance(op_r, Imm):
        t_val = ctx.fresh_temp()
        pre_r = ei_r + [IConst(t_val, op_r.value)]
        val = t_val
        tm_r = tm_r + [t_val]
    else:
        pre_r = ei_r
        val = op_r.name
    pre_slot, slot_a, tm_sl = _pool_call_slot_arg(ctx, t_slot)
    ins = (
        pre_m
        + pre_r
        + pre_slot
        + [
            ICall(
                "__mn_pool_store",
                [slot_a, val] + list(_ptr_pool_mem_names(ctx)),
            )
        ]
    )
    all_tm = tm_m + tm_r + tm_sl + [t_slot]
    if all_tm:
        ctx.use_scratch = True
    post = [IHistPush(ctx.scratch, x) for x in reversed(all_tm)]
    return ins + post


def _lower_deref_assign_phys(ptr_phys: str, rhs: c.Node, ctx: _Ctx) -> list[Instr]:
    """`*ptr = rhs` con `ptr_phys` già un nome variabile Kairos (es. __mn_e0)."""
    _register_ptr_pool_locals(ctx)
    ei, op, temps = _eval_expr(rhs, ctx)
    ctx.use_hist = True
    if isinstance(op, Imm):
        t = ctx.fresh_temp()
        pre = ei + [IConst(t, op.value)]
        val = t
        temps = temps + [t]
    else:
        pre = ei
        val = op.name
    if temps:
        ctx.use_scratch = True
    pre_slot, slot_a, tm_sl = _pool_call_slot_arg(ctx, ptr_phys)
    if tm_sl:
        ctx.use_scratch = True
    ins = pre + pre_slot + [
        ICall(
            "__mn_pool_store",
            [slot_a, val] + list(_ptr_pool_mem_names(ctx)),
        )
    ]
    post = [IHistPush(ctx.scratch, x) for x in reversed(temps + tm_sl)]
    return ins + post


def _lower_assign(lhs: str, rhs: c.Node, ctx: _Ctx) -> list[Instr]:
    ei, op, temps = _eval_expr(rhs, ctx)
    ctx.use_hist = True
    if temps:
        ctx.use_scratch = True
    out: list[Instr] = ei + [IHistPush(ctx.hist, lhs), IAddEq(lhs, op)]
    for tmp in reversed(temps):
        out.append(IHistPush(ctx.scratch, tmp))
    return out


def _lower_array_subscript_assign(
    base: str, subs: list[c.Node], rhs: c.Node, ctx: _Ctx
) -> list[Instr]:
    if base not in ctx.array_info:
        raise MnemoCompileError(f"array {base!r} non dichiarato")
    info = ctx.array_info[base]
    if len(subs) != len(info.dims):
        raise MnemoCompileError(
            f"array {base!r}: servono {len(info.dims)} indici nell'lvalue"
        )
    ei, op, tm_r = _eval_expr(rhs, ctx)
    ctx.use_hist = True
    if isinstance(op, Imm):
        t = ctx.fresh_temp()
        pre_r = ei + [IConst(t, op.value)]
        val = t
        tm_r = tm_r + [t]
    else:
        pre_r = ei
        val = op.name
    if tm_r:
        ctx.use_scratch = True

    if all(isinstance(s, c.Constant) for s in subs):
        lin = _const_row_major_linear(subs, info.dims)
        cell = _array_elem_local(base, lin)
        cp = _phys(ctx, cell)
        out = pre_r + [IHistPush(ctx.hist, cp), IAddEq(cp, Var(val))]
        for tmp in reversed(tm_r):
            out.append(IHistPush(ctx.scratch, tmp))
        return out

    idx_expr = _c_row_major_index_ast(subs, info.dims, None)
    pre_i, op_ix, tm_i = _eval_expr(idx_expr, ctx)
    if isinstance(op_ix, Imm):
        tix = ctx.fresh_temp()
        pre_i = pre_i + [IConst(tix, op_ix.value)]
        ix = tix
        tm_i = tm_i + [tix]
    else:
        ix = op_ix.name

    bodies = [
        [
            IHistPush(ctx.hist, _phys(ctx, _array_elem_local(base, kk))),
            IAddEq(_phys(ctx, _array_elem_local(base, kk)), Var(val)),
        ]
        for kk in range(info.total)
    ]
    chain = _disj_eq_chain(ix, list(range(info.total)), bodies)
    out = pre_i + pre_r + chain
    for tmp in reversed(tm_i + tm_r):
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
        if expr.name in ctx.int_locals:
            return [], _phys(ctx, expr.name), []
        if expr.name in ctx.enum_constants:
            return [], str(ctx.enum_constants[expr.name]), []
        raise MnemoCompileError(
            f"condizione: variabile o enumeratore non noto {expr.name!r}"
        )
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
        if expr.name in ctx.int_locals:
            return [], (expr.name, "!=", "0"), []
        if expr.name in ctx.enum_constants:
            v = ctx.enum_constants[expr.name]
            if v == 0:
                return [], ("0", "==", "1"), []
            return [], ("0", "==", "0"), []
        raise MnemoCompileError(f"condizione: variabile non dichiarata {expr.name!r}")
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
    """
    Azzera il contatore di verità lc dopo un incremento (lc ∈ {0,1} per _build_truth_incr_lc).

    Stessa idea di `x = 0` reversibile: push(lc, hist) poi lc += 0 (senza __mn_mul_into né scratch).
    """
    ctx.use_hist = True
    return [IHistPush(ctx.hist, lc), IAddEq(lc, Imm(0))]


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
    noop_ct = _loop_body_continue_is_noop(node.stmt)
    stmts = (
        []
        if noop_ct
        else _flatten_stmt_to_list(node.stmt)
    )
    need_br = _has_break_targeting_loop(node.stmt, False)
    need_ct = _has_continue_targeting_loop(node.stmt, False) and not noop_ct
    br_v = ctx.fresh_temp() if need_br else None
    ct_v = ctx.fresh_loop_ct() if need_ct else None

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
    noop_ct = _loop_body_continue_is_noop(node.stmt)
    stmts = (
        []
        if noop_ct
        else _flatten_stmt_to_list(node.stmt)
    )
    need_br = _has_break_targeting_loop(node.stmt, False)
    need_ct = _has_continue_targeting_loop(node.stmt, False) and not noop_ct
    br_v = ctx.fresh_temp() if need_br else None
    ct_v = ctx.fresh_loop_ct() if need_ct else None

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
    noop_ct = _loop_body_continue_is_noop(node.stmt)
    if noop_ct:
        body_only: list[c.Node] = []
    elif isinstance(node.stmt, c.Compound):
        body_only = list(node.stmt.block_items or [])
    else:
        body_only = [node.stmt]

    lc = ctx.fresh_temp()
    need_br = _has_break_targeting_loop(node.stmt, False)
    need_ct = _has_continue_targeting_loop(node.stmt, False) and not noop_ct
    br_v = ctx.fresh_temp() if need_br else None
    ct_v = ctx.fresh_loop_ct() if need_ct else None
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


def _stmt_never_falls_through(node: c.Node | None) -> bool:
    """
    True se eseguendo `node` non si «cade» sulla successiva istruzione del blocco
    (return, break, continue, o blocco il cui ultimo statement è così).
    Usato per `if (c) then senza else` seguito da altre istruzioni: in C il resto
    è l'equivalente di un ramo else e non va emesso dopo `fi` (altrimenti la VM
    esegue sempre il codice dopo il costrutto if/fi).
    """
    if node is None:
        return False
    if isinstance(node, (c.Return, c.Break, c.Continue)):
        return True
    if isinstance(node, c.Compound):
        items = node.block_items or []
        if not items:
            return False
        return _stmt_never_falls_through(items[-1])
    if isinstance(node, c.If):
        if node.iffalse is None:
            return _stmt_never_falls_through(node.iftrue)
        return _stmt_never_falls_through(node.iftrue) and _stmt_never_falls_through(
            node.iffalse
        )
    return False


def _lower_compound_block_items(items: list[c.Node], ctx: _Ctx) -> list[Instr]:
    """Abbassa un blocco `{ ... }` con folding `if senza else` + coda → ramo else."""
    out: list[Instr] = []
    i = 0
    n = len(items)
    while i < n:
        it = items[i]
        if (
            isinstance(it, c.If)
            and it.iffalse is None
            and i + 1 < n
            and _stmt_never_falls_through(it.iftrue)
        ):
            then_instrs = _lower_substmt(it.iftrue, ctx)
            else_instrs = _lower_compound_block_items(items[i + 1 :], ctx)
            out.extend(_lower_if_from_expr(it.cond, then_instrs, else_instrs, ctx))
            return out
        out.extend(_lower_stmt(it, ctx))
        i += 1
    return out


def _lower_substmt(stmt: c.Node | None, ctx: _Ctx) -> list[Instr]:
    if stmt is None:
        return []
    if isinstance(stmt, c.Compound):
        return _lower_compound_block_items(list(stmt.block_items or []), ctx)
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
    items: list[c.Node], ctx: _Ctx
) -> list[tuple[str, list[c.Node]]]:
    cases: list[tuple[str, list[c.Node]]] = []
    for it in items:
        if isinstance(it, c.Case):
            if isinstance(it.expr, c.Constant):
                lab = str(_const_int(it.expr))
            elif isinstance(it.expr, c.ID) and it.expr.name in ctx.enum_constants:
                lab = str(ctx.enum_constants[it.expr.name])
            else:
                raise MnemoCompileError(
                    "switch: case richiede costante intera o enumeratore"
                )
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
    cases = _parse_switch_cases(node.stmt.block_items or [], ctx)
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

    if isinstance(node, c.Typedef):
        ctx.typedef_map[node.name] = node.type
        _maybe_register_struct_from_typedef(node.name, node.type, ctx.struct_specs)
        _maybe_register_union_from_typedef(node.name, node.type, ctx.union_specs)
        u = _strip_typedecl(node.type)
        if isinstance(u, c.Enum) and u.values:
            ctx.enum_constants.update(_enum_constants_from_enum(u))
        return []

    if isinstance(node, c.Decl):
        if isinstance(node.type, c.Union):
            un = node.type
            if un.decls:
                if un.name:
                    ctx.union_specs[un.name] = _union_scalar_fields(un)
                return []
            return []

        if isinstance(node.type, c.Enum) and node.type.values:
            ctx.enum_constants.update(_enum_constants_from_enum(node.type))
            return []

        if isinstance(node.type, c.Struct):
            st = node.type
            if st.decls:
                if st.name:
                    ctx.struct_specs[st.name] = _flatten_struct_fields(st)
                return []
            return []

        ut = _union_tag_for_decl_type(node.type, ctx)
        if ut is not None:
            if not isinstance(node.type, c.TypeDecl) or node.type.declname is None:
                raise MnemoCompileError("union: nome variabile mancante")
            varname = str(node.type.declname)
            if (
                varname in ctx.int_locals
                or varname in ctx.channel_kairos
                or varname in ctx.array_info
                or varname in ctx.struct_tag_of_var
                or varname in ctx.union_tag_of_var
            ):
                raise MnemoCompileError(f"ridichiarazione: {varname}")
            if ut not in ctx.union_specs:
                raise MnemoCompileError(f"union {ut}: definizione mancante")
            ctx.union_tag_of_var[varname] = ut
            ctx.int_locals.add(varname)
            if ctx.mem_layout is None:
                ctx.decl_order.append(varname)
            ctx.var_types[varname] = node.type
            if node.init is not None:
                raise MnemoCompileError("init union non supportato")
            return []

        st_tag = _struct_tag_for_decl_type(node.type, ctx)
        if st_tag is not None:
            if not isinstance(node.type, c.TypeDecl) or node.type.declname is None:
                raise MnemoCompileError("struct: nome variabile mancante")
            varname = str(node.type.declname)
            if (
                varname in ctx.int_locals
                or varname in ctx.channel_kairos
                or varname in ctx.array_info
                or varname in ctx.struct_tag_of_var
                or varname in ctx.union_tag_of_var
            ):
                raise MnemoCompileError(f"ridichiarazione: {varname}")
            fields = ctx.struct_specs.get(st_tag)
            if not fields:
                raise MnemoCompileError(f"struct {st_tag}: definizione mancante")
            ctx.struct_tag_of_var[varname] = st_tag
            for fn, fty in fields:
                loc = _struct_field_local(varname, fn)
                ctx.int_locals.add(loc)
                if ctx.mem_layout is None:
                    ctx.decl_order.append(loc)
                ctx.var_types[loc] = fty
            if node.init is not None:
                raise MnemoCompileError("init struct non supportato")
            return []

        ap = _try_parse_array_decl(node, ctx)
        if ap is not None:
            name, dims, esz = ap
            tot = int(math.prod(dims))
            if name in ctx.array_info or name in ctx.int_locals:
                raise MnemoCompileError(f"ridichiarazione: {name}")
            ctx.array_info[name] = _ArrayInfo(dims=dims, total=tot, elem_size=esz)
            ctx.var_types[name] = node.type
            for i in range(tot):
                cell = _array_elem_local(name, i)
                ctx.int_locals.add(cell)
                if ctx.mem_layout is None:
                    ctx.decl_order.append(cell)
            if node.init is None:
                return []
            if isinstance(node.init, c.InitList):
                flat = _flatten_init_list(node.init)
                out: list[Instr] = []
                for j, el in enumerate(flat):
                    if j >= tot:
                        break
                    out.extend(
                        _lower_assign(_phys(ctx, _array_elem_local(name, j)), el, ctx)
                    )
                return out
            raise MnemoCompileError(
                "array: inizializzatore `{ … }` oppure nessuno (non un singolo valore)"
            )

        imm = _immediate_named_scalar_typedef(node)
        if imm == "pthread_mutex_t":
            if not isinstance(node.type, c.TypeDecl) or node.type.declname is None:
                raise MnemoCompileError("pthread_mutex_t: nome variabile mancante")
            name = str(node.type.declname)
            if (
                name in ctx.int_locals
                or name in ctx.channel_kairos
                or name in ctx.array_info
                or name in ctx.struct_tag_of_var
                or name in ctx.union_tag_of_var
            ):
                raise MnemoCompileError(f"ridichiarazione: {name}")
            kai = f"__mn_mtx_{name}"
            ctx.channel_kairos[name] = kai
            ctx.channel_decl_order.append(name)
            ctx.var_types[name] = node.type
            if node.init is not None:
                raise MnemoCompileError("pthread_mutex_t: niente inizializzatore")
            return []

        td = ctx.typedef_map
        name = _scalar_decl_name(node, td)
        if name is None:
            name = _enum_scalar_decl_name(node)
        if name is None:
            pn = _int_ptr_var_decl_name(node, td)
            if pn is None:
                raise MnemoCompileError(
                    f"dichiarazione non supportata: {type(node.type).__name__}"
                )
            name = pn
        if (
            name in ctx.int_locals
            or name in ctx.channel_kairos
            or name in ctx.array_info
            or name in ctx.struct_tag_of_var
            or name in ctx.union_tag_of_var
        ):
            raise MnemoCompileError(f"ridichiarazione: {name}")
        ctx.int_locals.add(name)
        if ctx.mem_layout is None:
            ctx.decl_order.append(name)
        ctx.var_types[name] = node.type
        if node.init is None:
            return []
        if isinstance(node.init, c.InitList):
            raise MnemoCompileError("init struct/array non supportato")
        rhs_init = node.init
        if isinstance(rhs_init, c.ExprList):
            rhs_init = _fold_exprlist_as_comma_chain(rhs_init)
        return _lower_assign(_phys(ctx, name), rhs_init, ctx)

    if isinstance(node, c.Assignment):
        if (
            node.op == "="
            and isinstance(node.lvalue, c.ID)
            and isinstance(node.rvalue, c.FuncCall)
            and isinstance(node.rvalue.name, c.ID)
        ):
            lhs = node.lvalue.name
            if (
                lhs in ctx.struct_tag_of_var
                and ctx.mem_layout is not None
                and ctx.file_ast is not None
            ):
                callee = node.rvalue.name.name
                fd_u = _get_funcdef(ctx.file_ast, callee)
                if fd_u is not None and isinstance(fd_u.decl.type, c.FuncDecl):
                    callee_fd = fd_u.decl.type
                    tag = ctx.struct_tag_of_var[lhs]
                    fields = ctx.struct_specs.get(tag)
                    if fields:
                        sz_lhs = _sizeof_struct_tag(tag, ctx)
                        rw_lhs = _return_words_from_bytes(sz_lhs)
                        sz_ret = _sizeof_return_bytes(callee_fd, ctx)
                        rw_c = ctx.mem_layout.ret_words.get(callee, 0)
                        if (
                            sz_ret != sz_lhs
                            or rw_c != rw_lhs
                            or rw_c != len(fields)
                        ):
                            raise MnemoCompileError(
                                "assegnamento `struct = f()`: tipo di ritorno incompatibile"
                            )
                        sinks = [
                            _phys(ctx, _struct_field_local(lhs, fn))
                            for fn, _ in fields
                        ]
                        return _lower_funccall_with_ret(node.rvalue, ctx, sinks)
        if isinstance(node.lvalue, c.StructRef):
            if node.lvalue.type == "->":
                if node.op != "=":
                    raise MnemoCompileError("ptr->campo: solo `=` (niente += …)")
                return _lower_struct_arrow_assign(node.lvalue, node.rvalue, ctx)
            base, path = _structref_base_and_path(node.lvalue)
            mangled = "__".join(path)
            if base in ctx.union_tag_of_var:
                if len(path) != 1:
                    raise MnemoCompileError("union: un solo livello di campo")
                field = path[0]
                tag = ctx.union_tag_of_var[base]
                spec = ctx.union_specs.get(tag)
                if not spec or field not in [fn for fn, _ in spec]:
                    raise MnemoCompileError(f"union {tag}: membro {field!r} assente")
                compound_u = {
                    "+=": "+",
                    "-=": "-",
                    "*=": "*",
                    "/=": "/",
                    "%=": "%",
                    "^=": "^",
                }
                if node.op == "=":
                    return _lower_assign(_phys(ctx, base), node.rvalue, ctx)
                if node.op in compound_u:
                    rhs = c.BinaryOp(
                        compound_u[node.op],
                        node.lvalue,
                        node.rvalue,
                        node.coord,
                    )
                    return _lower_assign(_phys(ctx, base), rhs, ctx)
                raise MnemoCompileError(f"assegnamento union con {node.op!r} non supportato")
            if base not in ctx.struct_tag_of_var:
                raise MnemoCompileError(f"{base!r} non è una variabile struct")
            tag = ctx.struct_tag_of_var[base]
            spec = ctx.struct_specs.get(tag)
            if not spec or mangled not in [fn for fn, _ in spec]:
                raise MnemoCompileError(f"struct {tag}: campo {mangled!r} assente")
            cell = _struct_field_local(base, mangled)
            if node.op != "=":
                raise MnemoCompileError("struct: solo `=` (niente += …)")
            return _lower_assign(_phys(ctx, cell), node.rvalue, ctx)
        if isinstance(node.lvalue, c.ArrayRef):
            base, subs = _flatten_array_ref_chain(node.lvalue)
            if node.op != "=":
                raise MnemoCompileError("array[…]: solo `=` (niente += …)")
            return _lower_array_subscript_assign(base, subs, node.rvalue, ctx)
        if isinstance(node.lvalue, c.UnaryOp) and node.lvalue.op == "*":
            if node.op != "=":
                raise MnemoCompileError("assegnamento a *p: solo `=` (niente += …)")
            ei_p, op_p, tm_p = _eval_expr(node.lvalue.expr, ctx)
            if isinstance(op_p, Imm):
                tmp = ctx.fresh_temp()
                ei_p = ei_p + [IConst(tmp, op_p.value)]
                ptrn = tmp
                tm_p = tm_p + [tmp]
            elif isinstance(op_p, Var):
                ptrn = op_p.name
            else:
                raise MnemoCompileError("lvalue *expr: puntatore non valido")
            if ptrn not in ctx.int_locals:
                raise MnemoCompileError("lvalue *expr: operando non dichiarato")
            ctx.use_hist = True
            rest = _lower_deref_assign_phys(ptrn, node.rvalue, ctx)
            post = [IHistPush(ctx.scratch, x) for x in reversed(tm_p)]
            if tm_p:
                ctx.use_scratch = True
            return ei_p + rest + post
        if not isinstance(node.lvalue, c.ID):
            raise MnemoCompileError("lvalue non-ID non supportato")
        lhs = node.lvalue.name
        if lhs not in ctx.int_locals:
            raise MnemoCompileError(f"assegnamento a variabile non dichiarata: {lhs}")
        if node.op == "=":
            return _lower_assign(_phys(ctx, lhs), node.rvalue, ctx)
        compound = {"+=": "+", "-=": "-", "*=": "*", "/=": "/", "%=": "%", "^=": "^"}
        if node.op in compound:
            coord = node.coord
            # Nota Janus: `_lower_assign` fa eval(rhs) *prima* di push(lhs) che azzera lhs.
            # Per `sum += i` serve rhs = sum+i così il totale è calcolato prima del push.
            rhs = c.BinaryOp(
                compound[node.op],
                c.ID(_phys(ctx, lhs), coord),
                node.rvalue,
                coord,
            )
            return _lower_assign(_phys(ctx, lhs), rhs, ctx)
        raise MnemoCompileError(f"assegnamento con {node.op!r} non supportato")

    if isinstance(node, c.Cast):
        return _lower_discard_expr_result(node.expr, ctx)

    if getattr(c, "ExprStmt", None) is not None and isinstance(node, c.ExprStmt):
        if node.expr is None:
            return []
        return _lower_expr_as_stmt(node.expr, ctx)

    if isinstance(node, c.UnaryOp):
        return _lower_expr_as_stmt(node, ctx)

    if isinstance(node, c.FuncCall):
        if not isinstance(node.name, c.ID):
            raise MnemoCompileError("callee non è un identificatore")
        pthread_ins = _lower_pthread_mnemo_call(node, ctx)
        if pthread_ins is not None:
            if (
                ctx.is_main
                and isinstance(node.name, c.ID)
                and node.name.name == "mnemo_pthread_parallel2"
            ):
                ctx.after_par_join = True
            return pthread_ins
        nm = node.name.name
        if ctx.proc_returns_int.get(nm, False):
            if (
                ctx.mem_layout is not None
                and ctx.file_ast is not None
                and _get_funcdef(ctx.file_ast, nm) is not None
            ):
                rw_fn = ctx.mem_layout.ret_words.get(nm, 0)
                if rw_fn > 1:
                    return _lower_funccall_with_ret(node, ctx, None)
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
            if isinstance(node.expr, c.Constant):
                v = _const_int(node.expr)
                if v == 0:
                    return [IReturn()]
                ctx.use_hist = True
                return [
                    IHistPush(ctx.hist, "__mn_exit"),
                    IConst("__mn_exit", v),
                    IShow("__mn_exit"),
                    IReturn(),
                ]
            ei, op, temps = _eval_expr(node.expr, ctx)
            ctx.use_hist = True
            out: list[Instr] = list(ei)
            # Sempre `__mn_exit` + show: così `mnemo run` può usare il valore come exit code
            # (prima: show sul solo temporaneo es. __mn_e2, il parser non lo vedeva).
            out.extend(
                [
                    IHistPush(ctx.hist, "__mn_exit"),
                    IAddEq("__mn_exit", op),
                ]
            )
            for tmp in reversed(temps):
                out.append(IHistPush(ctx.scratch, tmp))
            if temps:
                ctx.use_scratch = True
            out.extend([IShow("__mn_exit"), IReturn()])
            return out
        if ctx.returns_int:
            if node.expr is None:
                raise MnemoCompileError("return senza espressione in funzione non-void")
            rw = len(ctx.ret_vars)
            if rw == 0:
                raise MnemoCompileError("return: layout ritorno mancante")
            if rw > 1:
                return _lower_return_aggregate(node.expr, ctx)
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
        return _lower_compound_block_items(list(node.block_items or []), ctx)

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

    if _file_ast_needs_ptr_pool(ast):
        needed.add("ptr_pool.kairos")

    order = [
        "helpers.kairos",
        "mul.kairos",
        "divmod.kairos",
        "mod.kairos",
        "ptr_pool.kairos",
    ]
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

    order = [
        "helpers.kairos",
        "mul.kairos",
        "divmod.kairos",
        "mod.kairos",
        "ptr_pool.kairos",
    ]
    head = [n for n in order if n in needed]
    tail = sorted(needed.difference(head))
    return head + tail


def _register_file_scope_struct_union_tags(
    ctx: _Ctx, file_ast: c.FileAST
) -> None:
    """
    In main le dichiarazioni file-scope popolano struct_tag_of_var / union_tag_of_var;
    nelle procedure utente va ripetuto, altrimenti `mps.client_done` non risolve `mps`.
    """
    for ext in file_ast.ext:
        if not isinstance(ext, c.Decl):
            continue
        if isinstance(ext.type, c.FuncDecl):
            continue
        if not isinstance(ext.type, c.TypeDecl) or ext.type.declname is None:
            continue
        vn = str(ext.type.declname)
        ut = _union_tag_for_decl_type(ext.type, ctx)
        if ut is not None:
            ctx.union_tag_of_var[vn] = ut
        st_tag = _struct_tag_for_decl_type(ext.type, ctx)
        if st_tag is not None:
            ctx.struct_tag_of_var[vn] = st_tag


def _locals_list(ctx: _Ctx) -> list[tuple[str, str]]:
    locals_list: list[tuple[str, str]] = []
    for n in ctx.decl_order:
        locals_list.append(("int", n))
    for logical in ctx.channel_decl_order:
        locals_list.append(("channel", ctx.channel_kairos[logical]))
    for n in sorted(
        (x for x in ctx.int_locals if x.startswith("__mn_e") and x[6:].isdigit()),
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
    *,
    defined_user_functions: frozenset[str],
    layout: ProgramMemLayout,
    file_ast: c.FileAST,
    ptr_pool_size: int,
    physical_mem_cells: int,
    file_td: dict[str, c.Node],
    file_specs: dict[str, list[tuple[str, c.Node]]],
    file_unions: dict[str, list[tuple[str, c.Node]]],
    file_enums: dict[str, int],
    file_scope_mutex_names: tuple[str, ...] = (),
) -> Function:
    name = fdef.decl.name
    fd = fdef.decl.type
    if not isinstance(fd, c.FuncDecl):
        raise MnemoCompileError("definizione funzione malformata")
    body = fdef.body
    if body is None or not isinstance(body, c.Compound):
        raise MnemoCompileError("corpo funzione non è un blocco { ... }")

    ret_int = proc_returns_int.get(name, False)

    ctx = _Ctx(
        extern_procs=callable_names,
        proc_returns_int=proc_returns_int,
        int_locals=set(),
        decl_order=[],
        param_names=frozenset(),
        is_main=False,
        returns_int=ret_int,
        ret_var=None,
        ptr_pool_size=ptr_pool_size,
        typedef_map=dict(file_td),
        struct_specs=dict(file_specs),
        union_specs=dict(file_unions),
        enum_constants=dict(file_enums),
        mem_layout=layout,
        file_ast=file_ast,
        total_mem_cells=layout.total_cells,
        physical_mem_cells=physical_mem_cells,
        heap_base=layout.heap_base,
        defined_user_functions=defined_user_functions,
    )
    _bind_ctx_layout(ctx, layout, name)
    ctx.file_scope_mutex_names = file_scope_mutex_names
    for m in file_scope_mutex_names:
        ctx.channel_kairos[m] = f"__mn_mtx_{m}"
    for (fk, n), _ in layout.slot_of.items():
        if fk == "__file__":
            ctx.int_locals.add(n)
    _register_file_scope_struct_union_tags(ctx, file_ast)
    for i in range(layout.total_cells):
        ctx.int_locals.add(f"__mn_mem{i}")
    if physical_mem_cells > layout.total_cells:
        for i in range(layout.total_cells, physical_mem_cells):
            n = f"__mn_mem{i}"
            ctx.int_locals.add(n)
            ctx.decl_order.append(n)
    param_order = [f"__mn_mem{i}" for i in range(layout.total_cells)]

    pm = _Ctx()
    pm.typedef_map = dict(file_td)
    pm.struct_specs = dict(file_specs)
    pm.union_specs = dict(file_unions)
    pm.enum_constants = dict(file_enums)
    pm.array_param_names = set()
    for p in _func_param_storage_names(fd, file_td, pm):
        ctx.int_locals.add(p)
    for r in _ret_slot_names(layout.ret_words.get(name, 0)):
        ctx.int_locals.add(r)
    for p in fd.args.params if fd.args else []:
        if isinstance(p, c.Decl):
            st_tag = _struct_tag_for_decl_type(p.type, ctx)
            if st_tag is not None and isinstance(p.type, c.TypeDecl):
                dn = p.type.declname
                if dn is not None:
                    ctx.struct_tag_of_var[str(dn)] = st_tag

    ctx.param_storage_order = tuple(_func_param_storage_names(fd, file_td, pm))

    _register_param_var_types(ctx, fd)

    instrs = _lower_compound_block_items(list(body.block_items or []), ctx)

    ch_formals = [("channel", ctx.channel_kairos[m]) for m in ctx.file_scope_mutex_names]
    return Function(
        name=name,
        params=[("int", p) for p in param_order] + ch_formals,
        locals=_locals_list(ctx),
        blocks=[Block("entry", [IComment(f"funzione C {name}")] + instrs)],
    )


def lower_file_to_program(
    ast: c.FileAST,
    *,
    main_argc: int = 0,
    ptr_pool_size: int = 4,
    layout: ProgramMemLayout | None = None,
    physical_mem_cells: int | None = None,
) -> Program:
    if not (1 <= ptr_pool_size <= PTR_POOL_MAX):
        raise MnemoCompileError(
            f"ptr_pool_size deve essere tra 1 e {PTR_POOL_MAX}, non {ptr_pool_size}"
        )
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

    file_td, file_specs, file_unions, file_enums = (
        collect_file_typedefs_structs_unions_enums(ast)
    )
    proc_returns_int = _merge_proc_returns_int(ast, file_td)
    du = frozenset(
        ext.decl.name
        for ext in ast.ext
        if isinstance(ext, c.FuncDef) and ext.decl.name and ext.decl.name != "main"
    )
    callable_names = _all_callable_names(ast) | PTHREAD_ABI_NAMES
    fs_mutexes = collect_file_scope_mutex_names(ast)

    if layout is None:
        layout = compute_program_mem_layout(ast, ptr_pool_size)
    phys = physical_mem_cells if physical_mem_cells is not None else layout.total_cells
    if phys < layout.total_cells:
        raise MnemoCompileError(
            f"physical_mem_cells ({phys}) < layout.total_cells ({layout.total_cells})"
        )

    user_fns: list[Function] = []
    for ext in ast.ext:
        if isinstance(ext, c.FuncDef) and ext.decl.name != "main":
            fname = ext.decl.name or ""
            needs_par_body = _func_body_uses_two_region_parallel(ast, fname)
            needs_par1_read = bool(layout.file_scope_partition1) and (
                _func_reads_partition1_file_vars(
                    ast, fname, layout.file_scope_partition1
                )
                and fname not in layout.parallel_region1_workers
            )
            fn_phys = (
                phys if (needs_par_body or needs_par1_read) else layout.total_cells
            )
            user_fns.append(
                _lower_user_function(
                    ext,
                    callable_names,
                    proc_returns_int,
                    defined_user_functions=du,
                    layout=layout,
                    file_ast=ast,
                    ptr_pool_size=ptr_pool_size,
                    physical_mem_cells=fn_phys,
                    file_td=file_td,
                    file_specs=file_specs,
                    file_unions=file_unions,
                    file_enums=file_enums,
                    file_scope_mutex_names=fs_mutexes,
                )
            )

    main_phys = (
        phys
        if (
            _func_body_uses_two_region_parallel(ast, "main")
            or (
                bool(layout.file_scope_partition1)
                and _func_reads_partition1_file_vars(
                    ast, "main", layout.file_scope_partition1
                )
            )
        )
        else layout.total_cells
    )

    ctx = _Ctx(
        extern_procs=callable_names,
        proc_returns_int=proc_returns_int,
        is_main=True,
        ptr_pool_size=ptr_pool_size,
        typedef_map=dict(file_td),
        struct_specs=dict(file_specs),
        union_specs=dict(file_unions),
        enum_constants=dict(file_enums),
        mem_layout=layout,
        file_ast=ast,
        total_mem_cells=layout.total_cells,
        physical_mem_cells=main_phys,
        heap_base=layout.heap_base,
        defined_user_functions=du,
    )
    _bind_ctx_layout(ctx, layout, "main")
    ctx.file_scope_mutex_names = fs_mutexes
    for m in fs_mutexes:
        ctx.channel_kairos[m] = f"__mn_mtx_{m}"
        ctx.channel_decl_order.append(m)
    for (fk, n), _ in layout.slot_of.items():
        if fk == "__file__":
            ctx.int_locals.add(n)
    _register_file_scope_struct_union_tags(ctx, ast)
    for name, _role in main_param_setup:
        ctx.int_locals.add(name)
    ctx.decl_order = [f"__mn_mem{i}" for i in range(main_phys)]
    ctx.decl_order.append("__mn_exit")
    for i in range(main_phys):
        ctx.int_locals.add(f"__mn_mem{i}")
    ctx.int_locals.add("__mn_exit")

    _register_param_var_types(ctx, mfd)

    if _file_ast_needs_ptr_pool(ast):
        _register_ptr_pool_locals(ctx)

    instrs: list[Instr] = []
    for name, role in main_param_setup:
        pn = _phys(ctx, name)
        if role == "argc":
            instrs.append(IConst(pn, main_argc))
        else:
            instrs.append(IConst(pn, 0))
    if _file_ast_needs_ptr_pool(ast):
        instrs.append(IConst(_PTR_POOL_CTR, layout.heap_base))

    instrs.extend(
        _lower_compound_block_items(list(body.block_items or []), ctx)
    )

    main_ir = Function(
        name="main",
        params=[],
        locals=_locals_list(ctx),
        blocks=[Block("entry", [IComment("generato da Mnemo da C")] + instrs)],
    )

    return Program(functions=user_fns + [main_ir])
