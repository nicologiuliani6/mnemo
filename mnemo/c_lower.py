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
- Tipi scalari: int, unsigned/uint (unsigned int), char, unsigned char, bool/_Bool; `typedef`; `enum` (costanti intere);
- I/O: `putchar(expr)`, `printf("fmt", …)` → `show(…, char)` / testo (vedi `MNEMO_IO_BUILTINS`).
- `char *p = "…"`: buffer sintetico + `\\0` in celle dedicate; `printf("%s", p)` se `p` è così inizializzato (non a livello file).
  `struct` (campi scalari, sott-struct annidate in linea); `union` (solo membri scalari, stesso int);
  passaggio `int a[N]` come `int*`.
- Espr.: operatore ternario `?:`, virgola (anche in `int x = (a, b);` come `ExprList`), XOR `^` e `^=`.
"""

from __future__ import annotations

import ast as pyast
import math
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import pycparser.c_ast as c

from mnemo.errors import MnemoCompileError
from mnemo.kairos_limits import MONOLITHIC_POOL_MEM_MAX, POOL_BANK_SIZE
from mnemo.layout_collect import ProgramMemLayout, compute_program_mem_layout
from mnemo.ptr_pool_kairos import PTR_POOL_MAX
from mnemo.ir import (
    Block,
    CmpOp,
    Function,
    IAddEq,
    ICall,
    IUncall,
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
    Operand,
    Var,
)

BUILTIN_KAIROS_PROCS = frozenset(
    {
        "__mn_mul_into",
        "__mn_divmod_nonneg",
        "__mn_mod_nonneg",
        "__mn_and_into",
        "__mn_or_into",
        "__mn_shl_into",
        "__mn_shr_into",
        "__mn_pool_alloc",
        "__mn_pool_store",
        "__mn_pool_load",
        "__mn_pool_free",
        "__mn_putd",
        "__mn_putd_uint",
        "__mn_putx",
        "__mn_putx_uint",
    }
)

# I/O host: gestiti nel lowering, non sono procedure Kairos.
MNEMO_IO_BUILTINS = frozenset({"putchar", "printf", "puts"})

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

# Assegnamento composto: `lhs op= rhs` → RHS `lhs op rhs` (lhs letto prima del push in `_lower_assign`).
_COMPOUND_ASSIGN_OPS: dict[str, str] = {
    "+=": "+",
    "-=": "-",
    "*=": "*",
    "/=": "/",
    "%=": "%",
    "^=": "^",
    "&=": "&",
    "|=": "|",
    "<<=": "<<",
    ">>=": ">>",
}

# mps.h: espansi al chiamante così i canali usano nomi reali (mps, req, …), non il parametro `m`.
MPS_INLINE_AT_CALLSITE = frozenset(
    {"init_mutexes", "destroy_mutexes", "ssend", "srecv"}
)

# Intrinsics → Kairos nativo ssend(<…>, ch) / srecv(<…>, ch) (tuple + channel passing).
MNEMO_PI_KAIROS_INTRINSICS = frozenset(
    {
        "mnemo_pi_ssend_request",
        "mnemo_pi_srecv_request",
        "mnemo_pi_ssend_reply",
        "mnemo_pi_srecv_reply",
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


def _func_is_recursive_user(ast: c.FileAST | None, fname: str) -> bool:
    """Ricorsione diretta o worker `parallel2(f, f, …)`: call+uncall da main non è applicabile."""
    if ast is None:
        return False
    fdef = _get_funcdef(ast, fname)
    if fdef is None or fdef.body is None:
        return False
    stack: list[c.Node | None] = [fdef.body]
    while stack:
        n = stack.pop()
        if n is None:
            continue
        if isinstance(n, c.FuncCall) and isinstance(n.name, c.ID):
            if n.name.name == fname:
                return True
            if n.name.name == "mnemo_pthread_parallel2" and n.args is not None:
                exprs = list(n.args.exprs) if isinstance(n.args, c.ExprList) else [n.args]
                for ex in exprs[:2]:
                    if isinstance(ex, c.ID) and ex.name == fname:
                        return True
        for _na, ch in n.children():
            if isinstance(ch, list):
                stack.extend(ch)
            elif ch is not None:
                stack.append(ch)
    return False


def infer_par2_workers_all(ast: c.FileAST) -> frozenset[str]:
    """Entrambi i worker (arg0 e arg1) di `mnemo_pthread_parallel2`.

    Usato da opt-uncall: il body di questi worker NON deve emettere il pattern
    snap/uncall interno, altrimenti par-uncall esterno fallisce DELOCAL.
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
                for ai in (0, 1):
                    a = exprs[ai]
                    if isinstance(a, c.ID):
                        out.add(a.name)
        for _na, ch in n.children():
            if isinstance(ch, list):
                stack.extend(ch)
            elif ch is not None:
                stack.append(ch)
    return frozenset(out)


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
        ("char",),
        ("unsigned", "char"),
        ("signed", "char"),
        ("short",),
        ("short", "int"),
        ("signed", "short"),
        ("signed", "short", "int"),
        ("unsigned", "short"),
        ("unsigned", "short", "int"),
        ("long",),
        ("long", "int"),
        ("signed", "long"),
        ("signed", "long", "int"),
        ("unsigned", "long"),
        ("unsigned", "long", "int"),
        ("long", "long"),
        ("signed", "long", "long"),
        ("unsigned", "long", "long"),
        ("_Bool",),
        ("bool",),
    }
)

_FLOATING_LEAF_NAMES = frozenset({"float", "double", "long double"})


def _reject_floating_leaf(leaf: c.Node, ctx: str) -> None:
    if isinstance(leaf, c.IdentifierType) and leaf.names:
        n0 = leaf.names[0]
        if n0 in _FLOATING_LEAF_NAMES or (
            len(leaf.names) >= 2
            and leaf.names[0] == "long"
            and leaf.names[1] == "double"
        ):
            raise MnemoCompileError(
                f"{ctx}: `float` / `double` non supportati nel modello intero Mnemo"
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
        _reject_floating_leaf(leaf, "tipo")
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


def _flatten_struct_fields(
    st: c.Struct,
    prefix: str = "",
    *,
    struct_specs: dict[str, list[tuple[str, c.Node]]] | None = None,
    typedef_map: dict[str, c.Node] | None = None,
) -> list[tuple[str, c.Node]]:
    """Campi struct con annidamento inline: `struct { int y; } n` → `prefix+n__y`.

    Se `struct_specs` viene passato, si espandono anche i campi che sono
    riferimenti per-nome a un'altra struct già definita (`struct Inner i`),
    producendo `prefix + i__<campo>` per ciascun campo di Inner. Senza
    `struct_specs` si lascia il campo nested come (prefix+fname, type), come
    in precedenza (back-compat per `union_flat_fields` / typedef pass).
    """
    out: list[tuple[str, c.Node]] = []
    for d in st.decls or []:
        if not isinstance(d, c.Decl) or not d.name:
            continue
        fname = str(d.name)
        cur = _strip_typedecl(d.type)
        if isinstance(cur, c.Struct) and cur.decls:
            out.extend(
                _flatten_struct_fields(
                    cur, prefix + fname + "__",
                    struct_specs=struct_specs, typedef_map=typedef_map,
                )
            )
        elif (
            struct_specs is not None
            and isinstance(cur, c.Struct)
            and cur.name
            and cur.name in struct_specs
        ):
            for sub_fn, sub_fty in struct_specs[cur.name]:
                out.append((prefix + fname + "__" + sub_fn, sub_fty))
        elif (
            struct_specs is not None
            and typedef_map is not None
            and isinstance(cur, c.IdentifierType)
            and len(cur.names) == 1
            and cur.names[0] in typedef_map
        ):
            leaf = _follow_typedef_chain(list(cur.names), typedef_map, set())
            if (
                isinstance(leaf, c.Struct)
                and leaf.name
                and leaf.name in struct_specs
            ):
                for sub_fn, sub_fty in struct_specs[leaf.name]:
                    out.append((prefix + fname + "__" + sub_fn, sub_fty))
            elif (
                isinstance(leaf, c.Struct)
                and leaf.decls
            ):
                out.extend(
                    _flatten_struct_fields(
                        leaf, prefix + fname + "__",
                        struct_specs=struct_specs, typedef_map=typedef_map,
                    )
                )
            else:
                out.append((prefix + fname, d.type))
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


def _maybe_register_struct_from_typedef(
    name: str,
    type_node: c.Node,
    specs: dict[str, list[tuple[str, c.Node]]],
    typedef_map: dict[str, c.Node] | None = None,
) -> None:
    u = _strip_typedecl(type_node)
    if isinstance(u, c.Struct) and u.decls:
        tag = u.name if u.name else name
        specs[tag] = _flatten_struct_fields(
            u, struct_specs=specs, typedef_map=typedef_map
        )


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
    # Two-pass: prima typedef (per popolare td), poi struct/union decls
    # (per il flatten che usa td su typedef-referenced fields).
    for ext in ast.ext:
        if isinstance(ext, c.Typedef):
            td[ext.name] = ext.type
            u = _strip_typedecl(ext.type)
            if isinstance(u, c.Enum) and u.values:
                enums.update(_enum_constants_from_enum(u))
    for ext in ast.ext:
        if isinstance(ext, c.Typedef):
            _maybe_register_struct_from_typedef(ext.name, ext.type, specs, typedef_map=td)
            _maybe_register_union_from_typedef(ext.name, ext.type, union_specs)
        elif isinstance(ext, c.Decl) and isinstance(ext.type, c.Struct):
            st = ext.type
            if st.decls and st.name:
                specs[st.name] = _flatten_struct_fields(
                    st, struct_specs=specs, typedef_map=td
                )
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
            cur = _eval_enum_init(ev.value, out)
        out[ev.name] = cur
        cur += 1
    return out


def _eval_enum_init(node: c.Node, prev: dict[str, int]) -> int:
    """Valuta a compile-time il valore di un enumeratore. Supporta Constant,
    UnaryOp `-`/`+`/`~`/`!`, BinaryOp aritmetici/bit/shift/cmp, ID che
    referenzia un enumeratore precedente (lookup in `prev`)."""
    if isinstance(node, c.Constant):
        return _literal_int_widen(node)
    if isinstance(node, c.ID):
        if node.name in prev:
            return prev[node.name]
        raise MnemoCompileError(f"enum init: identifier {node.name!r} non risolto")
    if isinstance(node, c.UnaryOp):
        v = _eval_enum_init(node.expr, prev)
        if node.op == "-":
            return -v
        if node.op == "+":
            return v
        if node.op == "~":
            return ~v
        if node.op == "!":
            return 1 if v == 0 else 0
        raise MnemoCompileError(f"enum init: unary {node.op!r} non supportato")
    if isinstance(node, c.BinaryOp):
        a = _eval_enum_init(node.left, prev)
        b = _eval_enum_init(node.right, prev)
        op = node.op
        if op == "+": return a + b
        if op == "-": return a - b
        if op == "*": return a * b
        if op == "/": return a // b if b else 0
        if op == "%": return a % b if b else 0
        if op == "|": return a | b
        if op == "&": return a & b
        if op == "^": return a ^ b
        if op == "<<": return a << b
        if op == ">>": return a >> b
        if op == "==": return int(a == b)
        if op == "!=": return int(a != b)
        if op == "<":  return int(a < b)
        if op == ">":  return int(a > b)
        if op == "<=": return int(a <= b)
        if op == ">=": return int(a >= b)
        if op == "&&": return int(bool(a) and bool(b))
        if op == "||": return int(bool(a) or bool(b))
        raise MnemoCompileError(f"enum init: binary {op!r} non supportato")
    raise MnemoCompileError(
        f"enum init: nodo {type(node).__name__} non supportato"
    )


@dataclass
class _ArrayInfo:
    """Row-major: `dims` = (d0,d1,…), `total` = ∏ dims, `elem_size` byte per elemento.
    `array_decay_pointer`: parametro `int a[R][C]` — storage è un puntatore base pool."""

    dims: tuple[int, ...]
    total: int
    elem_size: int = _SIZEOF_SCALAR
    array_decay_pointer: bool = False


@dataclass
class _LoopFrame:
    br_var: str | None
    ct_var: str | None


@dataclass
class _SwitchSeg:
    """Un gruppo di etichette case/default con lo stesso blocco di istruzioni iniziale."""

    values: list[str]
    stmts: list[c.Node]


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
    # Ordine dei canali file-scope passati in coda alle procedure: mutex `__mn_mtx_*` e π `__mn_kch_*`.
    file_scope_channel_order: tuple[str, ...] = ()
    """Dopo `mnemo_pthread_parallel2` in main: letture campi worker-1 usano la 2ª partizione."""
    after_par_join: bool = False
    """Logici (non-file-scope) letti dalla partizione 1 dopo `parallel2` nel frame corrente."""
    local_partition1_read_logicals: set[str] = field(default_factory=set)
    # char* = "…" → mappa nome puntatore → base array `__mn_ros_*` (per printf %s su quella variabile).
    char_ptr_string_base: dict[str, str] = field(default_factory=dict)
    """char* = \"literal\" → valore originale della stringa (per strlen/strcmp compile-time)."""
    char_ptr_string_value: dict[str, str] = field(default_factory=dict)
    """Slot logici dichiarati come puntatore a funzione (`int (*p)(int)`)."""
    func_ptr_vars: set[str] = field(default_factory=set)
    """Puntatore a funzione (nome logico) → nome procedura risolto a compile-time."""
    func_ptr_alias: dict[str, str] = field(default_factory=dict)
    """Scope blocchi: ogni frame mappa nome C → nome logico slot (shadowing)."""
    scope_stack: list[dict[str, str]] = field(default_factory=list)
    shadow_uid: int = 0
    """`&x` almeno una volta: non usare `__mn_v_x` in `_phys` (pool aggiorna `__mn_mem*`)."""
    addr_taken_logicals: set[str] = field(default_factory=set)
    """Stack Janus distinti per ogni ramo di `par` (la VM rifiuta lo stesso id in due branch)."""
    par_branch_stack_uid: int = 0
    par_branch_stack_names: list[str] = field(default_factory=list)
    # opt_uncall_user_calls: call → snap XOR di tutti i __mn_mem* → uncall → ripristino valori
    # post-call (xor-swap ×3); stack/canali kairos fuori dai mem non si snapshottano (uncall gestisce gli stack).
    opt_uncall_user_calls: bool = False
    """Nomi delle procedure dove l'IR (from/until, par, π) non tollera uncall con questa VM."""
    uncall_excluded_via_vm_targets: frozenset[str] = field(default_factory=frozenset)
    """Funzioni con ssend/srecv: niente opt-uncall single-call (inverse `srecv`
    si blocca in attesa senza counterpart). Par-uncall in parallel2 OK (entrambi
    i worker inversi si parlano simmetricamente)."""
    channel_using_targets: frozenset[str] = field(default_factory=frozenset)
    """Funzioni che sono worker di `mnemo_pthread_parallel2`: niente opt-uncall nei loro body
    (par-uncall esterno richiede body invertibili senza pattern snap/uncall interno)."""
    par2_workers: frozenset[str] = field(default_factory=frozenset)
    """Per ogni user fn, indici `__mn_mem<i>` che il body può toccare (transitivo).
    Usato da opt-uncall per snap solo celle effettivamente mutate."""
    callee_mem_touches: dict[str, frozenset[int]] = field(default_factory=dict)

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


def _kairos_stack_actuals(ctx: _Ctx) -> list[str]:
    """Argomenti `stack` passati al callee (stessa coppia del frame chiamante; `main` è l'unico senza formali)."""
    return [ctx.hist, ctx.scratch]


def _fresh_par_branch_stack_pair(ctx: _Ctx) -> tuple[str, str]:
    """
    Coppia `(hist, scratch)` dichiarabile come `local stack` sul chiamante: obbligatoria per
    `par` Kairos perché due rami non possono ricevere gli stessi identificatori di stack del caller.
    """
    i = ctx.par_branch_stack_uid
    ctx.par_branch_stack_uid += 1
    h = f"__mn_pb{i}_hist"
    s = f"__mn_pb{i}_scratch"
    ctx.par_branch_stack_names.extend([h, s])
    return h, s


def _scope_ensure(ctx: _Ctx) -> None:
    if not ctx.scope_stack:
        ctx.scope_stack = [{}]


def _scope_init_params(ctx: _Ctx, param_names: tuple[str, ...] | list[str]) -> None:
    ctx.scope_stack = [{}]
    ctx.shadow_uid = 0
    for p in param_names:
        ctx.scope_stack[-1][p] = p


def _scope_enter(ctx: _Ctx) -> None:
    _scope_ensure(ctx)
    ctx.scope_stack.append({})


def _scope_exit(ctx: _Ctx) -> None:
    if len(ctx.scope_stack) > 1:
        ctx.scope_stack.pop()


def _scope_resolve(ctx: _Ctx, source: str) -> str:
    _scope_ensure(ctx)
    for frame in reversed(ctx.scope_stack):
        if source in frame:
            return frame[source]
    return source


def _scope_declare(ctx: _Ctx, source: str) -> str:
    _scope_ensure(ctx)
    if source in ctx.scope_stack[-1]:
        raise MnemoCompileError(f"ridichiarazione: {source}")
    logical = source
    for frame in ctx.scope_stack[:-1]:
        if source in frame:
            logical = f"{source}__mn_sh{ctx.shadow_uid}"
            ctx.shadow_uid += 1
            break
    ctx.scope_stack[-1][source] = logical
    return logical


def _ptr_pool_mem_names(ctx: _Ctx) -> tuple[str, ...]:
    n = ctx.total_mem_cells if ctx.mem_layout is not None else ctx.ptr_pool_size
    return tuple(f"__mn_mem{i}" for i in range(n))


def _parallel_branch_mem_actuals(
    ctx: _Ctx, *, left: bool, callee_name: str | None = None
) -> list[str]:
    """
    Argomenti `call f(__mn_mem*, …)` per un ramo PAR a due worker.
    - Indici in `layout.parallel_file_shared_slots`: stesso actual `__mn_mem{i}` (memoria file-scope condivisa).
    - Altrimenti: ramo sinistro `__mn_mem{i}`, destro `__mn_mem{S+i}` (finestre disgiunte).
    - Se `callee_name` ha entry in `ctx.callee_mem_touches`, sottoinsieme delle celle toccate.
    """
    if ctx.mem_layout is None:
        raise MnemoCompileError("layout memoria mancante (parallel)")
    s = ctx.mem_layout.total_cells
    shared = ctx.mem_layout.parallel_file_shared_slots
    base = 0 if left else s
    if callee_name is not None:
        ct = ctx.callee_mem_touches.get(callee_name)
    else:
        ct = None
    idxs = sorted(ct) if ct is not None else list(range(s))
    out: list[str] = []
    for i in idxs:
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


def _pool_uses_banking(ctx: _Ctx) -> bool:
    if ctx.mem_layout is None:
        return False
    return ctx.total_mem_cells > MONOLITHIC_POOL_MEM_MAX


def _n_pool_banks(ctx: _Ctx) -> int:
    return math.ceil(ctx.total_mem_cells / POOL_BANK_SIZE)


def _ir_pool_divmod_slot(
    ctx: _Ctx, slot_var: str
) -> tuple[list[Instr], str, str, str]:
    t_b = ctx.fresh_temp()
    t_q = ctx.fresh_temp()
    t_r = ctx.fresh_temp()
    ctx.use_hist = True
    pre: list[Instr] = [
        IConst(t_b, POOL_BANK_SIZE),
        ICall(
            "__mn_divmod_nonneg",
            [slot_var, t_b, t_q, t_r] + _kairos_stack_actuals(ctx),
        ),
    ]
    return pre, t_b, t_q, t_r


def _bank_chain_pool_calls(
    ctx: _Ctx,
    t_q: str,
    proc_base: str,
    build_args: Callable[[int], list[str]],
) -> list[Instr]:
    """Albero di confronti su `t_q` (indice banca): meno `if` sequenziali che una catena lineare."""
    nb = _n_pool_banks(ctx)
    stk = _kairos_stack_actuals(ctx)
    if nb == 1:
        return [ICall(f"{proc_base}_b0", build_args(0) + stk)]

    def tree(lo: int, hi: int) -> list[Instr]:
        if hi - lo == 1:
            k = lo
            return [ICall(f"{proc_base}_b{k}", build_args(k) + stk)]
        mid = (lo + hi) // 2
        left = tree(lo, mid)
        right = tree(mid, hi)
        return [IIfKairos(t_q, "<", str(mid), left, right)]

    return tree(0, nb)


def _ir_pool_store_call(ctx: _Ctx, slot_var: str, val_var: str) -> list[Instr]:
    if not _pool_uses_banking(ctx):
        return [
            ICall(
                "__mn_pool_store",
                [slot_var, val_var]
                + list(_ptr_pool_mem_names(ctx))
                + _kairos_stack_actuals(ctx),
            )
        ]
    pre, _tb, t_q, t_r = _ir_pool_divmod_slot(ctx, slot_var)

    def args_for(bi: int) -> list[str]:
        s0 = bi * POOL_BANK_SIZE
        s1 = min(ctx.total_mem_cells, s0 + POOL_BANK_SIZE)
        return [t_r, val_var] + [f"__mn_mem{i}" for i in range(s0, s1)]

    return pre + _bank_chain_pool_calls(ctx, t_q, "__mn_pool_store", args_for)


def _ir_pool_load_call(ctx: _Ctx, slot_var: str, out_var: str) -> list[Instr]:
    if not _pool_uses_banking(ctx):
        return [
            ICall(
                "__mn_pool_load",
                [slot_var]
                + list(_ptr_pool_mem_names(ctx))
                + [out_var]
                + _kairos_stack_actuals(ctx),
            )
        ]
    pre, _tb, t_q, t_r = _ir_pool_divmod_slot(ctx, slot_var)

    def args_for(bi: int) -> list[str]:
        s0 = bi * POOL_BANK_SIZE
        s1 = min(ctx.total_mem_cells, s0 + POOL_BANK_SIZE)
        return [t_r] + [f"__mn_mem{i}" for i in range(s0, s1)] + [out_var]

    return pre + _bank_chain_pool_calls(ctx, t_q, "__mn_pool_load", args_for)


def _ir_pool_free_call(ctx: _Ctx, slot_var: str) -> list[Instr]:
    if not _pool_uses_banking(ctx):
        return [
            ICall(
                "__mn_pool_free",
                [slot_var]
                + list(_ptr_pool_mem_names(ctx))
                + [_PTR_POOL_CTR]
                + _kairos_stack_actuals(ctx),
            )
        ]
    pre, _tb, t_q, t_r = _ir_pool_divmod_slot(ctx, slot_var)

    def args_for(bi: int) -> list[str]:
        s0 = bi * POOL_BANK_SIZE
        s1 = min(ctx.total_mem_cells, s0 + POOL_BANK_SIZE)
        return [t_r] + [f"__mn_mem{i}" for i in range(s0, s1)] + [_PTR_POOL_CTR]

    return pre + _bank_chain_pool_calls(ctx, t_q, "__mn_pool_free", args_for)


def _phys(ctx: _Ctx, logical: str) -> str:
    """
    Nome Kairos per una variabile logica (cella __mn_mem{idx}).
    Variabili file-scope `("__file__", name)`: `__mn_p1_*` nel worker regione-1
    usano il formale `__mn_mem{idx}`; in main e nel resto usano `__mn_mem{S+idx}`.
    """
    hit = ctx.mem_phys.get(logical)
    if hit is not None:
        if (
            ctx.after_par_join
            and ctx.mem_layout is not None
            and (
                (
                    ctx.fn_name == "main"
                    and (
                        logical in ctx.mem_layout.main_partition1_read_logicals
                        or logical in ctx.mem_layout.file_scope_partition1
                    )
                )
                or logical in ctx.local_partition1_read_logicals
            )
        ):
            idx = ctx.slot_index.get(logical)
            if idx is not None:
                s = ctx.mem_layout.total_cells
                return f"__mn_mem{s + idx}"
        if logical in ctx.addr_taken_logicals:
            return hit
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
    if isinstance(cur, c.TypeDecl) and isinstance(cur.type, c.Enum):
        return _SIZEOF_SCALAR
    return None


def _try_parse_array_decl(
    node: c.Decl, ctx: _Ctx
) -> tuple[str, tuple[int, ...], int] | None:
    """
    Ritorna `(nome, dims, sizeof_elemento)` per dichiarazioni array, altrimenti `None`.
    Per la prima dimensione (outermost) inferisce la dim dall'init quando assente:
    - `int a[] = {1,2,3}` → 3
    - `char s[] = "abc"`  → 4 (incl. NUL)
    """
    cur = node.type
    dims: list[int] = []
    first = True
    while isinstance(cur, c.ArrayDecl):
        if cur.dim is None and first and node.init is not None:
            init = node.init
            if isinstance(init, c.InitList):
                dims.append(len(init.exprs or []))
            elif (
                isinstance(init, c.Constant) and init.type == "string"
            ):
                s = _literal_c_string(init)
                dims.append(len(s.encode("utf-8")) + 1)
            else:
                dims.append(_array_dim_const(cur.dim))
        else:
            dims.append(_array_dim_const(cur.dim))
        cur = cur.type
        first = False
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


def _array_init_dense_1d(init: c.InitList, array_size: int) -> list[c.Node | None]:
    """Per `int a[N] = {...}` produce lista densa di lunghezza N.
    Supporta init posizionali e designated `[idx] = val`. Indici mancanti
    restano None (cell già a 0 dopo decl). Mix positional/designated:
    designated resetta il cursore a idx+1 (standard C99).
    """
    out: list[c.Node | None] = [None] * array_size
    pos = 0
    for e in init.exprs:
        if isinstance(e, c.NamedInitializer):
            if len(e.name) != 1:
                raise MnemoCompileError(
                    "designated init: solo `[idx] = expr` 1D supportato"
                )
            d = e.name[0]
            if not isinstance(d, c.Constant):
                raise MnemoCompileError(
                    "designated init: indice deve essere costante intera"
                )
            try:
                idx = int(d.value, 0)
            except (TypeError, ValueError):
                raise MnemoCompileError(
                    f"designated init: indice non intero '{d.value}'"
                )
            if not (0 <= idx < array_size):
                raise MnemoCompileError(
                    f"designated init: indice {idx} fuori range [0,{array_size})"
                )
            out[idx] = e.expr
            pos = idx + 1
        else:
            if pos >= array_size:
                break
            out[pos] = e
            pos += 1
    return out


def _array_init_dense_nd(init: c.InitList, dims: list[int]) -> list[c.Node | None]:
    """Multi-D designated/nested: row-major flat output.

    Supporta:
    - full-index designator: `[r][c]=val`
    - partial-index designator + nested InitList: `[r]={a,b,c}`
    - nested InitList senza designator: `{{1,2,3},{4,5,6}}` (riga per riga)
    - mix posizionale/designated (avanza cursore lineare)
    """
    tot = 1
    for d in dims:
        tot *= d
    out: list[c.Node | None] = [None] * tot

    def fill_block(start: int, sub_dims: list[int], val: c.Node) -> int:
        """Place `val` at flat offset starting at `start`. Returns new cursor."""
        stride = 1
        for d in sub_dims:
            stride *= d
        if isinstance(val, c.InitList) and sub_dims:
            sub = _array_init_dense_nd(val, sub_dims)
            for i, v in enumerate(sub):
                if v is not None:
                    out[start + i] = v
            return start + stride
        if isinstance(val, c.InitList) and not sub_dims:
            raise MnemoCompileError(
                "designated init: lista annidata su scalare non supportata"
            )
        out[start] = val
        return start + (stride if sub_dims else 1)

    pos = 0
    for e in init.exprs:
        if isinstance(e, c.NamedInitializer):
            if len(e.name) > len(dims):
                raise MnemoCompileError(
                    f"designated init multi-D: troppi indici "
                    f"(atteso ≤{len(dims)}, dato {len(e.name)})"
                )
            base = 0
            for k, d in enumerate(e.name):
                if not isinstance(d, c.Constant):
                    raise MnemoCompileError(
                        "designated init: indice deve essere costante intera"
                    )
                try:
                    ix = int(d.value, 0)
                except (TypeError, ValueError):
                    raise MnemoCompileError(
                        f"designated init: indice non intero '{d.value}'"
                    )
                if not (0 <= ix < dims[k]):
                    raise MnemoCompileError(
                        f"designated init: indice {ix} fuori range [0,{dims[k]})"
                    )
                base = base * dims[k] + ix
            sub_dims = dims[len(e.name):]
            stride = 1
            for d in sub_dims:
                stride *= d
            base *= stride
            pos = fill_block(base, sub_dims, e.expr)
        else:
            if pos >= tot:
                break
            if isinstance(e, c.InitList) and len(dims) > 1:
                row_size = 1
                for d in dims[1:]:
                    row_size *= d
                row_start = (pos // row_size) * row_size
                pos = fill_block(row_start, dims[1:], e)
            else:
                out[pos] = e
                pos += 1
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


def collect_file_scope_kairos_pi_channels(ast: c.FileAST) -> tuple[str, ...]:
    """Nomi di `mnemo_kairos_channel_t` a livello file (canali π nativi Kairos, tuple ssend/srecv)."""
    out: list[str] = []
    for ext in ast.ext:
        if isinstance(ext, (c.FuncDef, c.Typedef)):
            continue
        if not isinstance(ext, c.Decl):
            continue
        if isinstance(ext.type, c.FuncDecl):
            continue
        if _immediate_named_scalar_typedef(ext) != "mnemo_kairos_channel_t":
            continue
        if not isinstance(ext.type, c.TypeDecl) or ext.type.declname is None:
            continue
        out.append(str(ext.type.declname))
    return tuple(sorted(out))


def file_scope_channel_order(
    mutex_names: tuple[str, ...], pi_channels: tuple[str, ...]
) -> tuple[str, ...]:
    return tuple(sorted(frozenset(mutex_names) | frozenset(pi_channels)))


def _type_node_is_pthread_mutex(ty: c.Node, _td: dict[str, c.Node]) -> bool:
    """True se il tipo (es. campo struct) è dichiarato come `pthread_mutex_t` (typedef)."""
    cur: c.Node | None = ty
    while isinstance(cur, c.TypeDecl):
        cur = cur.type
    return isinstance(cur, c.IdentifierType) and cur.names == ["pthread_mutex_t"]


def collect_mutex_channel_keys(
    ast: c.FileAST,
    struct_specs: dict[str, list[tuple[str, c.Node]]],
    td: dict[str, c.Node],
) -> tuple[str, ...]:
    """
    Chiavi canali mutex: variabili file-scope `pthread_mutex_t` + una chiave per ogni
    campo mutex di ogni *istanza* struct (`nome_var__tag__campo`), così due `mps_t`
    locali non condividono gli stessi canali π della VM.
    """
    keys: set[str] = set(collect_file_scope_mutex_names(ast))
    mini = _Ctx(typedef_map=dict(td), struct_specs=dict(struct_specs))

    def add_struct_var(varname: str, st_tag: str) -> None:
        fields = struct_specs.get(st_tag)
        if not fields:
            return
        for fnm, fty in fields:
            if _type_node_is_pthread_mutex(fty, td):
                keys.add(f"{varname}__{st_tag}__{fnm}")

    def collect_params(fd: c.FuncDecl) -> None:
        if fd.args is None:
            return
        for p in fd.args.params:
            if not isinstance(p, c.Decl):
                continue
            if isinstance(p.type, c.PtrDecl):
                inner = p.type.type
                st2 = _struct_tag_for_decl_type(inner, mini)
                if st2 is not None and isinstance(inner, c.TypeDecl) and inner.declname:
                    add_struct_var(str(inner.declname), st2)
                continue
            st = _struct_tag_for_decl_type(p.type, mini)
            if st is not None:
                decl = p.type
                while isinstance(decl, (c.PtrDecl, c.ArrayDecl)):
                    decl = decl.type
                if isinstance(decl, c.TypeDecl) and decl.declname:
                    add_struct_var(str(decl.declname), st)

    def walk_struct_decls(node: c.Node | None) -> None:
        if node is None:
            return
        if isinstance(node, c.Decl):
            st_tag = _struct_tag_for_decl_type(node.type, mini)
            if st_tag is not None:
                decl = node.type
                while isinstance(decl, (c.PtrDecl, c.ArrayDecl)):
                    decl = decl.type
                if isinstance(decl, c.TypeDecl) and decl.declname:
                    add_struct_var(str(decl.declname), st_tag)
        for _na, ch in node.children():
            if isinstance(ch, list):
                for x in ch:
                    walk_struct_decls(x)
            elif ch is not None:
                walk_struct_decls(ch)

    for ext in ast.ext:
        if isinstance(ext, c.FuncDef):
            continue
        if not isinstance(ext, c.Decl):
            continue
        if isinstance(ext.type, c.FuncDecl):
            continue
        st = _struct_tag_for_decl_type(ext.type, mini)
        if st is not None:
            decl = ext.type
            while isinstance(decl, (c.PtrDecl, c.ArrayDecl)):
                decl = decl.type
            if isinstance(decl, c.TypeDecl) and decl.declname:
                add_struct_var(str(decl.declname), st)

    for ext in ast.ext:
        if isinstance(ext, c.FuncDef):
            fname = ext.decl.name or ""
            fd = ext.decl.type
            if isinstance(fd, c.FuncDecl) and fname not in MPS_INLINE_AT_CALLSITE:
                collect_params(fd)
            if ext.body is not None:
                walk_struct_decls(ext.body)

    return tuple(sorted(keys))


def _file_scope_channel_actuals(ctx: _Ctx) -> list[str]:
    return [ctx.channel_kairos[m] for m in ctx.file_scope_channel_order]


def pthread_mutex_channel_key_for_par_check(
    arg: c.Node,
    fdef: c.FuncDef,
    td: dict[str, c.Node],
    struct_specs: dict[str, list[tuple[str, c.Node]]],
) -> str | None:
    """
    Ricava la stessa chiave canale usata dal lowering per `pthread_mutex_*(&…)`.
    Per `par_shared_mutex_check` (senza _Ctx pieno).
    """
    if not isinstance(arg, c.UnaryOp) or arg.op != "&":
        return None
    inner = arg.expr
    if isinstance(inner, c.ID):
        return inner.name
    if isinstance(inner, c.StructRef) and inner.type == "->":
        base, path = _structref_base_and_path(inner)
        mangled = "__".join(path)
        fd = fdef.decl.type
        if not isinstance(fd, c.FuncDecl) or fd.args is None:
            return None
        mini = _Ctx(typedef_map=dict(td), struct_specs=dict(struct_specs))
        for p in fd.args.params:
            if not isinstance(p, c.Decl):
                continue
            pname = p.name or _decl_basename_from_innermost(p.type)
            if pname != base:
                continue
            tag = _pointee_struct_tag(p.type, mini)
            fields = struct_specs.get(tag, [])
            if any(
                fn == mangled and _type_node_is_pthread_mutex(fty, td)
                for fn, fty in fields
            ):
                return f"{base}__{tag}__{mangled}"
            return None
        return None
    if isinstance(inner, c.StructRef) and inner.type == ".":
        base, path = _structref_base_and_path(inner)
        mangled = "__".join(path)
        fd = fdef.decl.type
        if not isinstance(fd, c.FuncDecl) or fd.args is None:
            return None
        mini = _Ctx(typedef_map=dict(td), struct_specs=dict(struct_specs))
        for p in fd.args.params:
            if not isinstance(p, c.Decl):
                continue
            pname = p.name or _decl_basename_from_innermost(p.type)
            if pname != base:
                continue
            tag = _struct_tag_for_decl_type(p.type, mini)
            if tag is None:
                return None
            fields = struct_specs.get(tag, [])
            if any(
                fn == mangled and _type_node_is_pthread_mutex(fty, td)
                for fn, fty in fields
            ):
                return f"{base}__{tag}__{mangled}"
            return None
        return None
    return None


def _pthread_mutex_channel_key(arg: c.Node, ctx: _Ctx) -> str:
    if not isinstance(arg, c.UnaryOp) or arg.op != "&":
        raise MnemoCompileError(
            "pthread_mutex_*: atteso &mutex, &ptr->campo o &s.campo (campo pthread_mutex_t)"
        )
    inner = arg.expr
    if isinstance(inner, c.ID):
        n = inner.name
        if n not in ctx.channel_kairos:
            raise MnemoCompileError(f"pthread_mutex_*: {n!r} non è un pthread_mutex_t noto")
        return n
    if isinstance(inner, c.StructRef) and inner.type == "->":
        base, path = _structref_base_and_path(inner)
        mangled = "__".join(path)
        pty = ctx.var_types.get(base)
        if pty is None:
            raise MnemoCompileError(
                f"pthread_mutex_*: tipo di {base!r} sconosciuto per &{base}->…"
            )
        tag = _pointee_struct_tag(pty, ctx)
        fields = ctx.struct_specs.get(tag)
        if not fields:
            raise MnemoCompileError(f"pthread_mutex_*: struct {tag!r} senza metadati")
        fty = None
        for fn, ft in fields:
            if fn == mangled:
                fty = ft
                break
        if fty is None or not _type_node_is_pthread_mutex(fty, ctx.typedef_map):
            raise MnemoCompileError(
                f"pthread_mutex_*: {tag}.{mangled} non è un campo pthread_mutex_t"
            )
        key = f"{base}__{tag}__{mangled}"
        if key not in ctx.channel_kairos:
            raise MnemoCompileError(f"pthread_mutex_*: chiave canale {key!r} non registrata")
        return key
    if isinstance(inner, c.StructRef) and inner.type == ".":
        base, path = _structref_base_and_path(inner)
        mangled = "__".join(path)
        tag = ctx.struct_tag_of_var.get(base)
        if tag is None:
            raise MnemoCompileError(
                f"pthread_mutex_*: {base!r} non è una variabile struct per `.` campo"
            )
        fields = ctx.struct_specs.get(tag)
        if not fields:
            raise MnemoCompileError(f"pthread_mutex_*: struct {tag!r} senza metadati")
        fty = None
        for fn, ft in fields:
            if fn == mangled:
                fty = ft
                break
        if fty is None or not _type_node_is_pthread_mutex(fty, ctx.typedef_map):
            raise MnemoCompileError(
                f"pthread_mutex_*: {tag}.{mangled} non è un campo pthread_mutex_t"
            )
        key = f"{base}__{tag}__{mangled}"
        if key not in ctx.channel_kairos:
            raise MnemoCompileError(f"pthread_mutex_*: chiave canale {key!r} non registrata")
        return key
    raise MnemoCompileError(
        "pthread_mutex_*: atteso &mutex, &ptr->campo o &s.campo (campo pthread_mutex_t)"
    )


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


def _func_param_group_is_pi_channel(
    group: list[str], fd: c.FuncDecl, td: dict[str, c.Node]
) -> bool:
    """Un solo slot con nome di un parametro `mnemo_kairos_channel_t`."""
    if len(group) != 1:
        return False
    n = group[0]
    if fd.args is None:
        return False
    for p in fd.args.params:
        if not isinstance(p, c.Decl):
            continue
        if _immediate_named_scalar_typedef(p) != "mnemo_kairos_channel_t":
            continue
        if not isinstance(p.type, c.TypeDecl) or p.type.declname is None:
            continue
        if str(p.type.declname) == n:
            return True
    return False


def _call_pi_channel_kairos_names(
    fd: c.FuncDecl, raw_exprs: list[c.Node], ctx: _Ctx
) -> list[str]:
    """Per ogni parametro `mnemo_kairos_channel_t`, nome Kairos del canale passato come `&x`."""
    if fd.args is None:
        return []
    out: list[str] = []
    for p, ex in zip(fd.args.params, raw_exprs):
        if not isinstance(p, c.Decl):
            continue
        if _immediate_named_scalar_typedef(p) != "mnemo_kairos_channel_t":
            continue
        if not isinstance(ex, c.UnaryOp) or ex.op != "&" or not isinstance(ex.expr, c.ID):
            raise MnemoCompileError(
                "passaggio canale π: atteso `&nome` con `nome` di tipo "
                "`mnemo_kairos_channel_t`"
            )
        vn = ex.expr.name
        if vn not in ctx.channel_kairos:
            raise MnemoCompileError(
                f"passaggio canale π: `{vn}` non è un canale π noto nel contesto del chiamante"
            )
        out.append(ctx.channel_kairos[vn])
    return out


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
    fg: list[list[str]] = []
    fr: list[c.Node] = []
    for g, e in zip(groups, raw_exprs):
        if _func_param_group_is_pi_channel(g, fd, ctx.typedef_map):
            continue
        fg.append(g)
        fr.append(e)
    layout = ctx.mem_layout
    lead_arg, flat_exprs = _flatten_user_call_arguments(fr, fg, ctx, layout)
    if len(flat_exprs) != len(param_logs):
        raise MnemoCompileError(
            f"worker `{fname}`: mismatch tra argomenti appiattiti e slot nel layout"
        )
    s = layout.total_cells
    pre: list[Instr] = []
    pre.extend(lead_arg)

    # Snapshot di tutti gli argomenti prima di qualsiasi store nei __mn_mem* del worker:
    # evita che un assegnamento precoce (es. n := n-1) alteri i successivi (es. n-2).
    snap_vals: list[tuple[str, str]] = []
    for ex, log_key in zip(flat_exprs, param_logs):
        ei, op, tm = _eval_expr(ex, ctx)
        t_snap = ctx.fresh_temp()
        pre.extend(ei)
        pre.append(IHistPush(ctx.hist, t_snap))
        pre.append(IAddEq(t_snap, op if isinstance(op, Imm) else Var(op.name)))
        if tm:
            ctx.use_scratch = True
            pre.extend([IHistPush(ctx.scratch, x) for x in reversed(tm)])
        snap_vals.append((log_key, t_snap))

    for log_key, t_snap in snap_vals:
        key = (fname, log_key)
        if key not in layout.slot_of:
            raise MnemoCompileError(
                f"worker `{fname}`: slot parametro {log_key!r} assente nel layout"
            )
        idx = layout.slot_of[key]
        phys = mem_partition_index * s + idx
        dst = f"__mn_mem{phys}"
        pre.extend(_lower_assign(dst, c.ID(t_snap, None), ctx))
    if snap_vals:
        ctx.use_scratch = True
        pre.extend([IHistPush(ctx.scratch, t) for _k, t in reversed(snap_vals)])
    return pre


def _pthread_worker_param_assign_plan(
    fname: str,
    raw_exprs: list[c.Node],
    ctx: _Ctx,
    *,
    mem_partition_index: int,
) -> tuple[list[Instr], list[tuple[str, c.Node]]]:
    """Piano assegnamenti parametri worker: `lead` + coppie (dst_phys, expr)."""
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
    fg: list[list[str]] = []
    fr: list[c.Node] = []
    for g, e in zip(groups, raw_exprs):
        if _func_param_group_is_pi_channel(g, fd, ctx.typedef_map):
            continue
        fg.append(g)
        fr.append(e)
    layout = ctx.mem_layout
    lead_arg, flat_exprs = _flatten_user_call_arguments(fr, fg, ctx, layout)
    if len(flat_exprs) != len(param_logs):
        raise MnemoCompileError(
            f"worker `{fname}`: mismatch tra argomenti appiattiti e slot nel layout"
        )
    s = layout.total_cells
    pairs: list[tuple[str, c.Node]] = []
    for ex, log_key in zip(flat_exprs, param_logs):
        key = (fname, log_key)
        if key not in layout.slot_of:
            raise MnemoCompileError(
                f"worker `{fname}`: slot parametro {log_key!r} assente nel layout"
            )
        idx = layout.slot_of[key]
        phys = mem_partition_index * s + idx
        pairs.append((f"__mn_mem{phys}", ex))
    return lead_arg, pairs


def _premirror_main_partition1_reads_before_par(ctx: _Ctx) -> list[Instr]:
    """
    Copia ogni locale `main` letto dopo il PAR dalla 2ª partizione:
    `__mn_mem{idx}` → `__mn_mem{S+idx}` subito prima del `PAR`.
    Il worker destro usa indici slot-locali che mappano sulla finestra destra;
    senza questa copia, il valore iniziale resterebbe solo nella metà sinistra.
    """
    if ctx.mem_layout is None:
        return []
    layout = ctx.mem_layout
    logs = layout.main_partition1_read_logicals
    if not logs:
        return []
    s = layout.total_cells
    if ctx.physical_mem_cells < 2 * s:
        raise MnemoCompileError(
            "pre-PAR mirror partizione: `physical_mem_cells` < 2·S — impossibile"
        )
    coord = None
    out: list[Instr] = []
    for log in sorted(logs):
        midx = layout.slot_of.get(("main", log))
        if midx is None:
            continue
        src = f"__mn_mem{midx}"
        dst = f"__mn_mem{s + midx}"
        out.append(IComment(f"pre-PAR mirror `{log}`: {dst} += {src}"))
        out.extend(_lower_assign(dst, c.ID(src, coord), ctx))
    return out


def _mark_parallel2_right_partition_reads(ctx: _Ctx, raw_exprs: list[c.Node]) -> None:
    """
    In funzioni non-main, se il worker destro riceve `&x`, dopo il join le letture di `x`
    devono usare la partizione destra (`__mn_mem{S+idx}`), coerente con i parametri del
    secondo ramo.
    """
    if ctx.mem_layout is None:
        return
    for ex in raw_exprs:
        if not isinstance(ex, c.UnaryOp) or ex.op != "&":
            continue
        inner = ex.expr
        if not isinstance(inner, c.ID):
            continue
        log = _scope_resolve(ctx, inner.name)
        if log in ctx.slot_index:
            ctx.local_partition1_read_logicals.add(log)


def _parallel2_retvalue_copies_to_addr_taken(
    ctx: _Ctx,
    fname: str,
    raw_exprs: list[c.Node],
    *,
    mem_partition_index: int,
) -> list[Instr]:
    """
    Se un worker `parallel2` restituisce `int` e un argomento è `&x`,
    copia il valore di ritorno nella variabile puntata (`x`) dopo il join.
    Questo rende usabile anche il pattern ricorsivo stile `fib(int n, int *ret)`.
    """
    if ctx.mem_layout is None:
        return []
    if ctx.mem_layout.ret_words.get(fname, 0) != 1:
        return []
    ret_key = (fname, MN_RET)
    if ret_key not in ctx.mem_layout.slot_of:
        return []
    s = ctx.mem_layout.total_cells
    ret_idx = ctx.mem_layout.slot_of[ret_key]
    ret_phys = mem_partition_index * s + ret_idx
    src = c.ID(f"__mn_mem{ret_phys}", None)
    out: list[Instr] = []
    for ex in raw_exprs:
        if not isinstance(ex, c.UnaryOp) or ex.op != "&" or not isinstance(ex.expr, c.ID):
            continue
        log = _scope_resolve(ctx, ex.expr.name)
        if log not in ctx.slot_index:
            continue
        dst = f"__mn_mem{ctx.slot_index[log]}"
        out.extend(_lower_assign(dst, src, ctx))
    return out


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
        _ct0 = ctx.callee_mem_touches.get(f0)
        if _ct0 is None:
            mem_args = [f"__mn_mem{i}" for i in range(ctx.mem_layout.total_cells)]
        else:
            mem_args = [f"__mn_mem{i}" for i in sorted(_ct0)]
        chx = _file_scope_channel_actuals(ctx)
        stk = _kairos_stack_actuals(ctx)
        return [IPar([[ICall(f0, mem_args + chx + stk)]])]

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
        _ct0 = ctx.callee_mem_touches.get(f0)
        if _ct0 is None:
            mem_args = [f"__mn_mem{i}" for i in range(ctx.mem_layout.total_cells)]
        else:
            mem_args = [f"__mn_mem{i}" for i in sorted(_ct0)]
        chx = _file_scope_channel_actuals(ctx)
        ctx.use_hist = True
        stk = _kairos_stack_actuals(ctx)
        return pre + [IPar([[ICall(f0, mem_args + chx + stk)]])]

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
        wh, ws = _fresh_par_branch_stack_pair(ctx)
        ch_h, ch_s = _fresh_par_branch_stack_pair(ctx)
        return [
            IPar(
                [
                    [
                        ICall(
                            f_work,
                            _parallel_branch_mem_actuals(ctx, left=False, callee_name=f_work) + chx + [wh, ws],
                        )
                    ],
                    [
                        ICall(
                            f_cont,
                            _parallel_branch_mem_actuals(ctx, left=True, callee_name=f_cont) + chx + [ch_h, ch_s],
                        )
                    ],
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
        wh, ws = _fresh_par_branch_stack_pair(ctx)
        ch_h, ch_s = _fresh_par_branch_stack_pair(ctx)
        return pre + [
            IPar(
                [
                    [
                        ICall(
                            f_work,
                            _parallel_branch_mem_actuals(ctx, left=False, callee_name=f_work) + chx + [wh, ws],
                        )
                    ],
                    [
                        ICall(
                            f_cont,
                            _parallel_branch_mem_actuals(ctx, left=True, callee_name=f_cont) + chx + [ch_h, ch_s],
                        )
                    ],
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
        # Fallback sequenziale solo se questo frame è uno dei due worker E i worker
        # prendono almeno un `int` (o `int *`) come arg: altrimenti `IPar(left=f0,right=f1)`
        # partiziona `__mn_mem*` in due finestre da S celle, e ogni livello ricorsivo
        # richiederebbe Ω(2^profondità) celle fisiche che non allochiamo. Quando i
        # worker prendono *solo* canali π (`mnemo_kairos_channel_t`), non c'è
        # nessuna cella `__mn_mem*` partizionata → real `par … and … rap` è sicuro
        # anche in ricorsione (fib via canali, vedi c_test/fib.c).
        def _worker_args_all_channels(fd: c.FuncDecl) -> bool:
            if fd.args is None:
                return True
            for p in fd.args.params:
                if not isinstance(p, c.Decl):
                    continue
                if _immediate_named_scalar_typedef(p) != "mnemo_kairos_channel_t":
                    return False
            return True
        _both_only_channels = _worker_args_all_channels(fd0) and _worker_args_all_channels(fd1)
        recursive_fallback = (ctx.fn_name in {f0, f1}) and not _both_only_channels
        pre: list[Instr] = []
        pre.extend(_premirror_main_partition1_reads_before_par(ctx))
        if expected_len > 2:
            lead0, pairs0 = _pthread_worker_param_assign_plan(
                f0, raw0, ctx, mem_partition_index=0
            )
            lead1, pairs1 = _pthread_worker_param_assign_plan(
                f1, raw1, ctx, mem_partition_index=1
            )
            pre.extend(lead0)
            pre.extend(lead1)
            snap_pairs = pairs0 + pairs1
            snap_vals: list[tuple[str, str]] = []
            for dst, ex in snap_pairs:
                ei, op, tm = _eval_expr(ex, ctx)
                t_snap = ctx.fresh_temp()
                pre.extend(ei)
                pre.append(IHistPush(ctx.hist, t_snap))
                pre.append(IAddEq(t_snap, op if isinstance(op, Imm) else Var(op.name)))
                if tm:
                    ctx.use_scratch = True
                    pre.extend([IHistPush(ctx.scratch, x) for x in reversed(tm)])
                snap_vals.append((dst, t_snap))
            for dst, t_snap in snap_vals:
                pre.extend(_lower_assign(dst, c.ID(t_snap, None), ctx))
            if snap_vals:
                ctx.use_scratch = True
                pre.extend([IHistPush(ctx.scratch, t) for _d, t in reversed(snap_vals)])
            ctx.use_hist = True
        chx = _file_scope_channel_actuals(ctx)
        pi0 = _call_pi_channel_kairos_names(fd0, raw0, ctx)
        pi1 = _call_pi_channel_kairos_names(fd1, raw1, ctx)
        left_mem_actuals = _parallel_branch_mem_actuals(ctx, left=True, callee_name=f0)
        right_mem_actuals = _parallel_branch_mem_actuals(ctx, left=False, callee_name=f1)
        lh, ls = _fresh_par_branch_stack_pair(ctx)
        rh, rs = _fresh_par_branch_stack_pair(ctx)
        left_args = left_mem_actuals + pi0 + chx + [lh, ls]
        right_args = right_mem_actuals + pi1 + chx + [rh, rs]
        left_call = ICall(f0, left_args)
        right_call = ICall(f1, right_args)
        post: list[Instr] = []
        post.extend(
            _parallel2_retvalue_copies_to_addr_taken(
                ctx, f0, raw0, mem_partition_index=0
            )
        )
        post.extend(
            _parallel2_retvalue_copies_to_addr_taken(
                ctx, f1, raw1, mem_partition_index=1
            )
        )
        if recursive_fallback:
            return pre + [IComment("parallel2 ricorsivo: fallback sequenziale"), left_call, right_call] + post
        par = IPar([[left_call], [right_call]])
        par_uncall_eligible = (
            ctx.opt_uncall_user_calls
            and f0 not in ctx.uncall_excluded_via_vm_targets
            and f1 not in ctx.uncall_excluded_via_vm_targets
            and not _func_is_recursive_user(ctx.file_ast, f0)
            and not _func_is_recursive_user(ctx.file_ast, f1)
        )
        if par_uncall_eligible:
            snap_temps: list[tuple[int, str]] = []
            snap_xors_post: list[Instr] = []
            t0 = ctx.callee_mem_touches.get(f0)
            t1 = ctx.callee_mem_touches.get(f1)
            cells_to_snap: set[int] = set()
            if t0 is None:
                cells_to_snap.update(range(ctx.physical_mem_cells))
            else:
                for actual in left_mem_actuals:
                    ci = _mem_idx_or_none(actual)
                    if ci is not None:
                        cells_to_snap.add(ci)
            if t1 is None:
                cells_to_snap.update(range(ctx.physical_mem_cells))
            else:
                for actual in right_mem_actuals:
                    ci = _mem_idx_or_none(actual)
                    if ci is not None:
                        cells_to_snap.add(ci)
            cell_iter = sorted(c for c in cells_to_snap if c < ctx.physical_mem_cells)
            for kk in cell_iter:
                t_cell = ctx.fresh_temp()
                snap_temps.append((kk, t_cell))
                snap_xors_post.append(IXorEq(t_cell, Var(f"__mn_mem{kk}")))
            uncall_par = IPar(
                [[IUncall(f0, left_args)], [IUncall(f1, right_args)]]
            )
            swap_ops: list[Instr] = []
            for kk, t_cell in snap_temps:
                mk = f"__mn_mem{kk}"
                swap_ops.extend(
                    [
                        IXorEq(mk, Var(t_cell)),
                        IXorEq(t_cell, Var(mk)),
                        IXorEq(mk, Var(t_cell)),
                    ]
                )
            body: list[Instr] = (
                [IComment("opt-uncall su par/rap: snap mem → par → diff → par-uncall → swap")]
                + [par]
                + snap_xors_post
                + [uncall_par]
                + swap_ops
            )
            return pre + body + post
        return pre + [par] + post

    if nm == "pthread_mutex_init":
        if len(exprs) != 2:
            raise MnemoCompileError("pthread_mutex_init: attesi 2 argomenti")
        vn = _pthread_mutex_channel_key(exprs[0], ctx)
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
        vn = _pthread_mutex_channel_key(exprs[0], ctx)
        ch = ctx.channel_kairos[vn]
        t = ctx.fresh_temp()
        ctx.use_hist = True
        return [
            IComment("pthread_mutex_lock → srecv token (π-style)"),
            ISrecv([t], ch),
            ISubEq(t, Imm(1)),
        ]

    if nm == "pthread_mutex_unlock":
        if len(exprs) != 1:
            raise MnemoCompileError("pthread_mutex_unlock: atteso 1 argomento")
        vn = _pthread_mutex_channel_key(exprs[0], ctx)
        ch = ctx.channel_kairos[vn]
        tok = ctx.fresh_temp()
        ctx.use_hist = True
        return [IConst(tok, 1), ISsend(ch, [tok])]

    if nm == "pthread_mutex_destroy":
        if len(exprs) != 1:
            raise MnemoCompileError("pthread_mutex_destroy: atteso 1 argomento")
        vn = _pthread_mutex_channel_key(exprs[0], ctx)
        ch = ctx.channel_kairos[vn]
        t = ctx.fresh_temp()
        ctx.use_hist = True
        return [
            IComment("pthread_mutex_destroy: svuota token residuo sul canale (prima del delocal)"),
            ISrecv([t], ch),
            ISubEq(t, Imm(1)),
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
        if _type_node_is_pthread_mutex(fty, ctx.typedef_map):
            continue
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
    """Puntatore a scalare (`int*`, `char*`, `unsigned*`, anche con più `*`).
    Anche pointer-to-array di scalare: `int (*p)[N]` lowered come `int*`."""
    cur = node.type
    if not isinstance(cur, c.PtrDecl):
        return None
    inner = cur.type
    while isinstance(inner, c.PtrDecl):
        inner = inner.type
    # `int (*p)[N]`: scendi attraverso ArrayDecl per arrivare al TypeDecl scalare.
    declname_from_array = None
    if isinstance(inner, c.ArrayDecl):
        # PtrDecl(ArrayDecl): il declname è sul PtrDecl interno o sul TypeDecl
        # in fondo. pycparser annida ArrayDecl(TypeDecl); estraiamo il nome
        # navigando fino al TypeDecl finale.
        a = inner
        while isinstance(a, c.ArrayDecl):
            a = a.type
        if isinstance(a, c.TypeDecl) and a.declname is not None:
            declname_from_array = str(a.declname)
            inner = a
        else:
            return None
    if not isinstance(inner, c.TypeDecl):
        return None
    if not isinstance(inner.type, c.IdentifierType):
        return None
    try:
        ex = _expand_typedef_names(list(inner.type.names), td)
    except MnemoCompileError:
        return None
    if tuple(ex) not in (
        ("int",),
        ("unsigned", "int"),
        ("unsigned",),
        ("char",),
        ("unsigned", "char"),
        ("void",),
        ("short",),
        ("short", "int"),
        ("long",),
        ("long", "int"),
        ("unsigned", "short"),
        ("unsigned", "long"),
        ("_Bool",),
        ("bool",),
    ):
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


def _cast_accepts_pointer_or_scalar(cast_node: c.Cast, ctx: _Ctx) -> bool:
    td = ctx.typedef_map
    tt = cast_node.to_type
    if isinstance(tt, c.TypeDecl) and isinstance(tt.type, c.IdentifierType):
        if tt.type.names == ["void"]:
            return True
        return _is_scalar_type_names(tt.type.names, td)
    if isinstance(tt, c.Typename):
        q = tt.type
        # Scalar cast: `(int)x`, `(unsigned)x`, `(long)x`, ecc.
        if isinstance(q, c.TypeDecl) and isinstance(q.type, c.IdentifierType):
            if q.type.names == ["void"]:
                return True
            return _is_scalar_type_names(q.type.names, td)
        if isinstance(q, c.PtrDecl):
            leaf = q
            while isinstance(leaf, c.PtrDecl):
                leaf = leaf.type
            if isinstance(leaf, c.TypeDecl) and isinstance(leaf.type, c.IdentifierType):
                nms = leaf.type.names
                if (
                    nms == ["void"]
                    or nms == ["int"]
                    or nms == ["char"]
                    or _is_scalar_type_names(nms, td)
                ):
                    return True
                if _struct_tag_for_decl_type(leaf, ctx) is not None:
                    return True
                if _union_tag_for_decl_type(leaf, ctx) is not None:
                    return True
    return False


def _decl_maybe_struct_typedef_pointer(node: c.Decl) -> bool:
    """`T *x` con T non riconosciuto come puntatore scalare (es. typedef struct)."""
    cur = node.type
    if not isinstance(cur, c.PtrDecl):
        return False
    inner = cur.type
    while isinstance(inner, c.PtrDecl):
        inner = inner.type
    if not isinstance(inner, c.TypeDecl) or inner.declname is None:
        return False
    if not isinstance(inner.type, c.IdentifierType):
        return False
    if _int_ptr_var_decl_name(node, {}) is not None:
        return False
    return True


def _file_ast_needs_ptr_pool(ast: c.FileAST) -> bool:
    def walk(node: object) -> bool:
        if node is None:
            return False
        if isinstance(node, c.Decl) and (
            _int_ptr_var_decl_name(node, {}) is not None
            or _decl_maybe_struct_typedef_pointer(node)
        ):
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


def _func_decl_has_variadic(fd: c.FuncDecl) -> bool:
    if fd.args is None:
        return False
    return any(isinstance(p, c.EllipsisParam) for p in fd.args.params)


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
            if _immediate_named_scalar_typedef(p) == "mnemo_kairos_channel_t":
                continue
            st_tag = _struct_tag_for_decl_type(p.type, ctx)
            if st_tag is not None:
                if not isinstance(p.type, c.TypeDecl) or p.type.declname is None:
                    raise MnemoCompileError("struct: nome parametro mancante")
                varname = str(p.type.declname)
                fields = ctx.struct_specs.get(st_tag)
                if not fields:
                    raise MnemoCompileError(f"struct {st_tag}: definizione mancante")
                for fn, fty in fields:
                    if _type_node_is_pthread_mutex(fty, td):
                        continue
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
                out.append(
                    [
                        _struct_field_local(varname, fn)
                        for fn, fty in fields
                        if not _type_node_is_pthread_mutex(fty, td)
                    ]
                )
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
    for n in MNEMO_IO_BUILTINS:
        sig[n] = False
    return sig


def _all_callable_names(ast: c.FileAST) -> frozenset[str]:
    s = set(BUILTIN_KAIROS_PROCS) | set(MNEMO_IO_BUILTINS)
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


_CONST_INT_TYPES = frozenset(
    {
        "int",
        "long",
        "unsigned int",
        "unsigned",
        "long long",
        "unsigned long",
        "unsigned long long",
        "short",
        "unsigned short",
    }
)


def _const_int(node: c.Constant) -> int:
    if node.type not in _CONST_INT_TYPES:
        raise MnemoCompileError(f"letterale non int supportato: type={node.type!r}")
    return int(node.value.rstrip("uUlL"), 0)


def _literal_char_value(node: c.Constant) -> int:
    """Letterale C `char` / carattere (pycparser: type 'char', value es. \"'a'\")."""
    if node.type != "char":
        raise MnemoCompileError(f"atteso letterale char, type={node.type!r}")
    try:
        s = pyast.literal_eval(node.value)
    except (SyntaxError, ValueError) as e:
        raise MnemoCompileError(f"letterale char non valido: {node.value!r}") from e
    if not isinstance(s, str) or len(s) != 1:
        raise MnemoCompileError(f"letterale char non valido: {node.value!r}")
    return ord(s)


def _literal_int_widen(node: c.Constant) -> int:
    """Intero da letterale int o char (per `_eval_expr` e simili)."""
    if node.type == "char":
        return _literal_char_value(node)
    return _const_int(node)


def _literal_c_string(node: c.Constant) -> str:
    if node.type != "string":
        raise MnemoCompileError(
            f"atteso letterale stringa \"…\", type={node.type!r}"
        )
    try:
        out = pyast.literal_eval(node.value)
    except (SyntaxError, ValueError) as e:
        raise MnemoCompileError(f"stringa non valida: {node.value!r}") from e
    if not isinstance(out, str):
        raise MnemoCompileError(f"stringa non valida: {node.value!r}")
    return out


def _decl_is_char_pointer(node: c.Decl, td: dict[str, c.Node]) -> bool:
    cur = node.type
    if not isinstance(cur, c.PtrDecl):
        return False
    inner = cur.type
    if not isinstance(inner, c.TypeDecl) or not isinstance(inner.type, c.IdentifierType):
        return False
    try:
        ex = tuple(_expand_typedef_names(list(inner.type.names), td))
    except MnemoCompileError:
        return False
    return ex in (("char",), ("unsigned", "char"))


def _char_ptr_string_literal_meta(
    node: c.Decl, td: dict[str, c.Node], fn: str
) -> tuple[str, int, bytes] | None:
    """
    `char *p = "…"`: base sintetica, numero di celle (byte + NUL), payload UTF-8 senza NUL.
    `int *p = "…"` → errore. Nessun init stringa → None.
    """
    if node.init is None or not isinstance(node.init, c.Constant):
        return None
    if node.init.type != "string":
        return None
    pn = _int_ptr_var_decl_name(node, td)
    if pn is None:
        return None
    if not _decl_is_char_pointer(node, td):
        raise MnemoCompileError(
            "inizializzatore stringa \"…\" ammesso solo per char* / unsigned char*"
        )
    s = _literal_c_string(node.init)
    b = s.encode("utf-8", errors="replace")
    if len(b) + 1 > ARR_MAX:
        raise MnemoCompileError(
            f"stringa letterale troppo lunga (max {ARR_MAX - 1} byte)"
        )
    tot = len(b) + 1
    sbase = f"__mn_ros_{fn}_{pn}"
    return (sbase, tot, b)


def _parse_printf_format(fmt: str) -> list[tuple]:
    """
    Segmenti printf: ('lit', testo), ('c',), ('d',), ('u',), ('x',), ('p',), ('s',).
    `%%` → ('lit', '%').
    """
    out: list[tuple] = []
    i = 0
    buf: list[str] = []
    while i < len(fmt):
        if fmt[i] == "%" and i + 1 < len(fmt):
            if buf:
                out.append(("lit", "".join(buf)))
                buf = []
            # Length modifiers (no-op nel word-VM): `l`, `ll`, `h`, `hh`,
            # `z`, `j`, `t`. Salta prima di leggere la conversion specifier.
            j = i + 1
            while j < len(fmt) and fmt[j] in ("l", "h", "z", "j", "t"):
                j += 1
            if j >= len(fmt):
                raise MnemoCompileError(
                    "printf: specificatore di conversione mancante dopo `%`"
                )
            spec = fmt[j]
            if spec == "%":
                buf.append("%")
            elif spec == "c":
                out.append(("c",))
            elif spec in ("d", "i"):
                out.append(("d",))
            elif spec == "u":
                out.append(("u",))
            elif spec == "x":
                out.append(("x",))
            elif spec == "p":
                out.append(("p",))
            elif spec == "s":
                out.append(("s",))
            else:
                raise MnemoCompileError(
                    f"printf: conversione non supportata %{spec!r} "
                    f"(supportati %%c %%d %%i %%u %%x %%p %%s %%%% e testo)"
                )
            i = j + 1
        else:
            buf.append(fmt[i])
            i += 1
    if buf:
        out.append(("lit", "".join(buf)))
    return out


def _ir_emit_byte_as_show_char(
    ctx: _Ctx, byte: int
) -> tuple[list[Instr], list[str]]:
    """Un byte su stdout come `show(tmp, char)` con tmp ripristinato a 0."""
    t = ctx.fresh_temp()
    v = int(byte) & 0xFF
    ins: list[Instr] = [
        IConst(t, v),
        IShow(t, True),
        ISubEq(t, Imm(v)),
    ]
    return ins, [t]


def _lower_putchar(expr: c.Node, ctx: _Ctx) -> list[Instr]:
    ei, op, tm = _eval_expr(expr, ctx)
    ctx.use_hist = True
    out: list[Instr] = list(ei)
    if isinstance(op, Imm):
        v = op.value & 0xFF
        ins, temps = _ir_emit_byte_as_show_char(ctx, v)
        out.extend(ins)
        tm = tm + temps
    elif isinstance(op, Var):
        out.append(IShow(op.name, True))
    else:
        raise MnemoCompileError("putchar: operando non valido")
    if tm:
        ctx.use_scratch = True
        out.extend([IHistPush(ctx.scratch, x) for x in reversed(tm)])
    return out


def _io_opt_uncall_wrap(ctx: "_Ctx", call_ins: "ICall") -> list[Instr]:
    """Pass-through: __mn_putd/__mn_putx hanno body con call ricorsive (__mn_putd_uint).
    `uncall` su questi triggera bug VM nel pass inverse profondo (SIGSEGV).
    Manteniamo solo la call forward; show è no-op in inverse, side effect rimane.
    """
    return [call_ins]


def _lower_printf(node: c.FuncCall, ctx: _Ctx) -> list[Instr]:
    def _format_hex_u32(v: int) -> str:
        return format(v & 0xFFFFFFFF, "x")

    if not isinstance(node.name, c.ID):
        raise MnemoCompileError("printf: callee non valido")
    el = node.args
    exprs = list(el.exprs) if el is not None else []
    if not exprs:
        raise MnemoCompileError("printf: serve almeno la stringa di formato")
    fmt_ex = exprs[0]
    if not isinstance(fmt_ex, c.Constant) or fmt_ex.type != "string":
        raise MnemoCompileError(
            'printf: il primo argomento deve essere un letterale "…"'
        )
    fmt = _literal_c_string(fmt_ex)
    pieces = _parse_printf_format(fmt)
    nargs = sum(1 for p in pieces if p[0] != "lit")
    if nargs != len(exprs) - 1:
        raise MnemoCompileError(
            f"printf: la stringa richiede {nargs} argomenti, "
            f"ne hai {len(exprs) - 1}"
        )
    out: list[Instr] = []
    tm_acc: list[str] = []
    arg_i = 1
    ctx.use_hist = True
    for piece in pieces:
        k = piece[0]
        if k == "lit":
            text = piece[1]
            for ch in text:
                ins, tt = _ir_emit_byte_as_show_char(ctx, ord(ch))
                out.extend(ins)
                tm_acc.extend(tt)
        elif k == "c":
            ex = exprs[arg_i]
            arg_i += 1
            ei, op, tm = _eval_expr(ex, ctx)
            out.extend(ei)
            if isinstance(op, Imm):
                ins, tt = _ir_emit_byte_as_show_char(ctx, op.value)
                out.extend(ins)
                tm_acc.extend(tm + tt)
            elif isinstance(op, Var):
                out.append(IShow(op.name, True))
                tm_acc.extend(tm)
            else:
                raise MnemoCompileError("printf %c: espressione non valida")
        elif k in ("d", "u"):
            ex = exprs[arg_i]
            arg_i += 1
            if isinstance(ex, c.Constant):
                val = _literal_int_widen(ex)
                for ch in str(val):
                    ins, tt = _ir_emit_byte_as_show_char(ctx, ord(ch))
                    out.extend(ins)
                    tm_acc.extend(tt)
            else:
                ei, op, tm = _eval_expr(ex, ctx)
                out.extend(ei)
                if isinstance(op, Imm):
                    for ch in str(op.value):
                        ins, tt = _ir_emit_byte_as_show_char(ctx, ord(ch))
                        out.extend(ins)
                        tm_acc.extend(tt)
                    tm_acc.extend(tm)
                elif isinstance(op, Var):
                    out.extend(
                        _io_opt_uncall_wrap(
                            ctx,
                            ICall("__mn_putd", [op.name] + _kairos_stack_actuals(ctx)),
                        )
                    )
                    tm_acc.extend(tm)
                else:
                    raise MnemoCompileError(f"printf %{k}: espressione non valida")
        elif k == "x":
            ex = exprs[arg_i]
            arg_i += 1
            if isinstance(ex, c.Constant):
                val = _literal_int_widen(ex)
                for ch in _format_hex_u32(val):
                    ins, tt = _ir_emit_byte_as_show_char(ctx, ord(ch))
                    out.extend(ins)
                    tm_acc.extend(tt)
            else:
                ei, op, tm = _eval_expr(ex, ctx)
                out.extend(ei)
                if isinstance(op, Imm):
                    for ch in _format_hex_u32(op.value):
                        ins, tt = _ir_emit_byte_as_show_char(ctx, ord(ch))
                        out.extend(ins)
                        tm_acc.extend(tt)
                    tm_acc.extend(tm)
                elif isinstance(op, Var):
                    out.extend(
                        _io_opt_uncall_wrap(
                            ctx,
                            ICall("__mn_putx", [op.name] + _kairos_stack_actuals(ctx)),
                        )
                    )
                    tm_acc.extend(tm)
                else:
                    raise MnemoCompileError("printf %x: espressione non valida")
        elif k == "p":
            ex = exprs[arg_i]
            arg_i += 1
            # Formato compatibile pratico: 0x + hex lowercase.
            ins0, tt0 = _ir_emit_byte_as_show_char(ctx, ord("0"))
            insx, ttx = _ir_emit_byte_as_show_char(ctx, ord("x"))
            out.extend(ins0 + insx)
            tm_acc.extend(tt0 + ttx)
            if isinstance(ex, c.Constant):
                val = _literal_int_widen(ex)
                for ch in _format_hex_u32(val):
                    ins, tt = _ir_emit_byte_as_show_char(ctx, ord(ch))
                    out.extend(ins)
                    tm_acc.extend(tt)
            else:
                ei, op, tm = _eval_expr(ex, ctx)
                out.extend(ei)
                if isinstance(op, Imm):
                    for ch in _format_hex_u32(op.value):
                        ins, tt = _ir_emit_byte_as_show_char(ctx, ord(ch))
                        out.extend(ins)
                        tm_acc.extend(tt)
                    tm_acc.extend(tm)
                elif isinstance(op, Var):
                    out.extend(
                        _io_opt_uncall_wrap(
                            ctx,
                            ICall("__mn_putx", [op.name] + _kairos_stack_actuals(ctx)),
                        )
                    )
                    tm_acc.extend(tm)
                else:
                    raise MnemoCompileError("printf %p: espressione non valida")
        elif k == "s":
            ex = exprs[arg_i]
            arg_i += 1
            if isinstance(ex, c.Constant) and ex.type == "string":
                raw = _literal_c_string(ex).encode("utf-8", errors="replace")
                for ch in raw:
                    ins, tt = _ir_emit_byte_as_show_char(ctx, ch)
                    out.extend(ins)
                    tm_acc.extend(tt)
            elif isinstance(ex, c.ID) and ex.name in ctx.char_ptr_string_base:
                sbase = ctx.char_ptr_string_base[ex.name]
                info = ctx.array_info.get(sbase)
                if info is None:
                    raise MnemoCompileError(
                        f"printf %s: storage stringa mancante per {ex.name!r}"
                    )
                for i in range(info.total - 1):
                    out.append(
                        IShow(_phys(ctx, _array_elem_local(sbase, i)), True)
                    )
            else:
                raise MnemoCompileError(
                    'printf %s: letterale "…" oppure char* da `char *x = "…";`'
                )
        else:
            raise MnemoCompileError("printf: segmento interno non valido")
    if tm_acc:
        ctx.use_scratch = True
        out.extend([IHistPush(ctx.scratch, x) for x in reversed(tm_acc)])
    return out


def _string_literal_value_of(expr: c.Node, ctx: _Ctx) -> str | None:
    """Restituisce il valore della stringa se `expr` è una stringa letterale
    o un `char *p = \"literal\";` con init costante. Altrimenti None."""
    if isinstance(expr, c.Constant) and expr.type == "string":
        return _literal_c_string(expr)
    if isinstance(expr, c.ID):
        log = _scope_resolve(ctx, expr.name)
        if log in ctx.char_ptr_string_value:
            return ctx.char_ptr_string_value[log]
    return None


def _try_eval_string_builtin(call: c.FuncCall, ctx: _Ctx) -> int | None:
    """`strlen(\"…\")` / `strlen(p)` (p inizializzato da literal) → len.
    `strcmp(a, b)` su due literal → sign(memcmp). None se runtime."""
    name = call.name.name
    args = call.args.exprs if call.args is not None else []
    if name == "strlen":
        if len(args) != 1:
            return None
        sv = _string_literal_value_of(args[0], ctx)
        if sv is None:
            return None
        return len(sv.encode("utf-8"))
    if name == "strcmp":
        if len(args) != 2:
            return None
        a = _string_literal_value_of(args[0], ctx)
        b = _string_literal_value_of(args[1], ctx)
        if a is None or b is None:
            return None
        ba = a.encode("utf-8")
        bb = b.encode("utf-8")
        if ba < bb:
            return -1
        if ba > bb:
            return 1
        return 0
    return None


def _resolve_offsetof_args(expr: c.FuncCall, ctx: _Ctx) -> int:
    """Resolve `__mn_offsetof_str("T-spec", "member-path")` → field-index * _SIZEOF_SCALAR.

    `T-spec` ∈ {"struct Name", "union Name", "TypedefName"}. `member-path`
    uses dotted notation (`a.b.c`); Mnemo flatten name uses `__`.
    Mnemo VM è word-VM: ogni scalare = _SIZEOF_SCALAR (4); alignment 4.
    Per union ogni campo ha offset 0.
    """
    args = expr.args.exprs if expr.args is not None else []
    if len(args) != 2:
        raise MnemoCompileError("__mn_offsetof_str: serve (type, member)")
    a0, a1 = args[0], args[1]
    if not (
        isinstance(a0, c.Constant) and a0.type == "string"
        and isinstance(a1, c.Constant) and a1.type == "string"
    ):
        raise MnemoCompileError("__mn_offsetof_str: args devono essere stringhe")
    type_spec = a0.value.strip('"')
    member = a1.value.strip('"')
    spec = type_spec.strip()
    fields: list[tuple[str, c.Node]] | None
    is_union = False
    if spec.startswith("struct "):
        tag = spec[len("struct "):].strip()
        fields = ctx.struct_specs.get(tag)
        if fields is None:
            raise MnemoCompileError(f"offsetof: struct {tag!r} non trovata")
    elif spec.startswith("union "):
        tag = spec[len("union "):].strip()
        fields = ctx.union_specs.get(tag)
        if fields is None:
            raise MnemoCompileError(f"offsetof: union {tag!r} non trovata")
        is_union = True
    else:
        if spec not in ctx.typedef_map:
            raise MnemoCompileError(f"offsetof: tipo {spec!r} non trovato")
        leaf = _follow_typedef_chain([spec], ctx.typedef_map, set())
        if isinstance(leaf, c.Union):
            tag = leaf.name if leaf.name else spec
            fields = ctx.union_specs.get(tag)
            if fields is None:
                raise MnemoCompileError(f"offsetof: union {tag!r} non risolta")
            is_union = True
        elif isinstance(leaf, c.Struct):
            tag = leaf.name if leaf.name else spec
            fields = ctx.struct_specs.get(tag)
            if fields is None:
                raise MnemoCompileError(f"offsetof: struct {tag!r} non risolta")
        else:
            raise MnemoCompileError(f"offsetof: {spec!r} non è struct/union")
    if is_union:
        return 0
    flat = member.replace(".", "__")
    assert fields is not None
    for idx, (fn, _ft) in enumerate(fields):
        if fn == flat:
            return idx * _SIZEOF_SCALAR
    raise MnemoCompileError(
        f"offsetof: campo {member!r} non trovato in {spec!r}"
    )


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
            if tuple(ex) in {("float",), ("double",), ("long", "double")}:
                raise MnemoCompileError("sizeof: float/double non supportati")
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


def _eval_decay_array_elem_read(
    base: str,
    subs: list[c.Node],
    info: _ArrayInfo,
    ctx: _Ctx,
    coord,
) -> tuple[list[Instr], Var, list[str]]:
    """Legge `base[i][…]` quando `base` è punatore-decay (parametro array)."""
    _register_ptr_pool_locals(ctx)
    coord_use = coord if coord is not None else getattr(subs[0], "coord", None)
    idx_expr = _c_row_major_index_ast(subs, info.dims, coord_use)
    pre_i, op_ix, tm_i = _eval_expr(idx_expr, ctx)
    ei_b, op_b, tm_b = _eval_expr(c.ID(base, coord_use), ctx)
    if isinstance(op_ix, Imm):
        ix_op: Operand = Imm(op_ix.value)
    else:
        ix_op = Var(op_ix.name)
    if isinstance(op_b, Imm):
        b_op: Operand = Imm(op_b.value)
    else:
        b_op = Var(op_b.name)
    t_slot = ctx.fresh_temp()
    ctx.use_hist = True
    pre = (
        ei_b
        + pre_i
        + [IHistPush(ctx.hist, t_slot), IAddEq(t_slot, b_op), IAddEq(t_slot, ix_op)]
    )
    pre_slot, slot_a, tm_sl = _pool_call_slot_arg(ctx, t_slot)
    if tm_sl:
        ctx.use_scratch = True
    t_out = ctx.fresh_temp()
    ins = pre + pre_slot + _ir_pool_load_call(ctx, slot_a, t_out)
    post = [IHistPush(ctx.scratch, x) for x in reversed(tm_i + tm_b + tm_sl)]
    if tm_i or tm_b or tm_sl:
        ctx.use_scratch = True
    return ins + post, Var(t_out), tm_b + tm_i + tm_sl + [t_slot, t_out]


def _lower_decay_array_subscript_assign(
    base: str,
    subs: list[c.Node],
    rhs: c.Node,
    info: _ArrayInfo,
    ctx: _Ctx,
) -> list[Instr]:
    """`*(`pool)[base+ix]` per parametro array decay."""
    _register_ptr_pool_locals(ctx)
    idx_expr = _c_row_major_index_ast(subs, info.dims, None)
    pre_i, op_ix, tm_i = _eval_expr(idx_expr, ctx)
    ei_b, op_b, tm_b = _eval_expr(c.ID(base, None), ctx)
    ei_r, op_r, tm_r = _eval_expr(rhs, ctx)
    ctx.use_hist = True
    if isinstance(op_r, Imm):
        t = ctx.fresh_temp()
        pre_r = ei_r + [IConst(t, op_r.value)]
        val = t
        tm_r = tm_r + [t]
    else:
        pre_r = ei_r
        val = op_r.name
    if tm_r:
        ctx.use_scratch = True
    if isinstance(op_ix, Imm):
        ix_op: Operand = Imm(op_ix.value)
    else:
        ix_op = Var(op_ix.name)
    if isinstance(op_b, Imm):
        b_op: Operand = Imm(op_b.value)
    else:
        b_op = Var(op_b.name)
    t_slot = ctx.fresh_temp()
    pre = (
        ei_b
        + pre_i
        + pre_r
        + [IHistPush(ctx.hist, t_slot), IAddEq(t_slot, b_op), IAddEq(t_slot, ix_op)]
    )
    pre_slot, slot_a, tm_sl = _pool_call_slot_arg(ctx, t_slot)
    if tm_sl:
        ctx.use_scratch = True
    ins = pre + pre_slot + _ir_pool_store_call(ctx, slot_a, val)
    post = [IHistPush(ctx.scratch, x) for x in reversed(tm_i + tm_b + tm_sl + tm_r)]
    return ins + post


def _eval_expr_into_var(expr: c.Node, ctx: _Ctx, target: str) -> list[Instr]:
    """Somma il valore di expr su `target` (target parte da 0)."""
    ei, op, tm = _eval_expr(expr, ctx)
    ctx.use_hist = True
    ins = ei + [IHistPush(ctx.hist, target), IAddEq(target, op)]
    post = [IHistPush(ctx.scratch, x) for x in reversed(tm)]
    if tm:
        ctx.use_scratch = True
    return ins + post


def _is_incdec_lvalue_shape(lv: c.Node) -> bool:
    if isinstance(lv, c.ID):
        return True
    if isinstance(lv, c.UnaryOp) and lv.op == "*":
        return True
    if isinstance(lv, c.StructRef):
        return lv.type in (".", "->")
    if isinstance(lv, c.ArrayRef):
        return True
    return False


def _lvalue_inc_dec_prefix_postfix(
    lv: c.Node, op: str, ctx: _Ctx
) -> tuple[list[Instr], Var | Imm, list[str]]:
    if op not in ("p++", "p--", "++", "--"):
        raise MnemoCompileError(f"operatore incremento non valido: {op!r}")
    if not _is_incdec_lvalue_shape(lv):
        raise MnemoCompileError(
            "++/--: lvalue richiesto (`x`, `*p`, `s.campo`, `p->campo`, `a[i]`)"
        )
    coord = getattr(lv, "coord", None)
    c1 = c.Constant("int", "1", coord)
    binop = "+" if op in ("p++", "++") else "-"
    ctx.use_hist = True
    if op in ("++", "--"):
        rhs = c.BinaryOp(binop, lv, c1, coord)
        st = c.Assignment("=", lv, rhs, coord)
        ei1 = _lower_stmt(st, ctx)
        ei2, op2, tm2 = _eval_expr(lv, ctx)
        return ei1 + ei2, op2, tm2
    t_old = ctx.fresh_temp()
    ei0 = _eval_expr_into_var(lv, ctx, t_old)
    rhs = c.BinaryOp(binop, c.ID(t_old, coord), c1, coord)
    st = c.Assignment("=", lv, rhs, coord)
    ei1 = _lower_stmt(st, ctx)
    return ei0 + ei1, Var(t_old), [t_old]


def _func_ptr_decl_meta(node: c.Decl, td: dict[str, c.Node]) -> tuple[str, c.FuncDecl] | None:
    """`int (*p)(int)` → (`p`, FuncDecl)."""
    cur = node.type
    if not isinstance(cur, c.PtrDecl):
        return None
    inner = cur.type
    while isinstance(inner, c.PtrDecl):
        inner = inner.type
    if not isinstance(inner, c.FuncDecl):
        return None
    if inner.args is None:
        return None
    if _func_decl_has_variadic(inner):
        return None
    rt = inner.type
    if not isinstance(rt, c.TypeDecl) or rt.declname is None:
        return None
    return str(rt.declname), inner


def _parse_function_designator(init: c.Node, ctx: _Ctx) -> str | None:
    if isinstance(init, c.ID):
        nm = init.name
        if nm in ctx.extern_procs or nm in ctx.defined_user_functions:
            return nm
        return None
    if isinstance(init, c.UnaryOp) and init.op == "&" and isinstance(init.expr, c.ID):
        return _parse_function_designator(init.expr, ctx)
    return None


def _resolve_indirect_callee(
    node: c.FuncCall, ctx: _Ctx
) -> tuple[c.FuncCall, str]:
    coord = getattr(node, "coord", None)
    if isinstance(node.name, c.ID):
        nm = node.name.name
        if nm in ctx.func_ptr_alias:
            nm = ctx.func_ptr_alias[nm]
        return c.FuncCall(c.ID(nm, coord), node.args, coord), nm
    if (
        isinstance(node.name, c.UnaryOp)
        and node.name.op == "*"
        and isinstance(node.name.expr, c.ID)
    ):
        idv = node.name.expr.name
        log = _scope_resolve(ctx, idv)
        if log not in ctx.func_ptr_alias:
            raise MnemoCompileError(
                "chiamata indiretta: puntatore non inizializzato con una funzione nota "
                "a compile-time (`p = f` o `p = &f` con `f` dichiarata)"
            )
        nm = ctx.func_ptr_alias[log]
        return c.FuncCall(c.ID(nm, coord), node.args, coord), nm
    raise MnemoCompileError(
        "chiamata: atteso nome funzione, variabile puntatore a funzione, o `(*p)(…)`"
    )


def _eval_expr(expr: c.Node, ctx: _Ctx) -> tuple[list[Instr], Var | Imm, list[str]]:
    if isinstance(expr, c.Constant):
        if expr.type == "string":
            raise MnemoCompileError(
                "letterale stringa non è un valore intero: usa printf(…) o char*"
            )
        return [], Imm(_literal_int_widen(expr)), []

    if isinstance(expr, c.ID):
        log = _scope_resolve(ctx, expr.name)
        if log in ctx.struct_tag_of_var:
            raise MnemoCompileError(
                f"{expr.name!r} è una struct: usa {expr.name}.campo"
            )
        if log in ctx.union_tag_of_var:
            raise MnemoCompileError(
                f"{expr.name!r} è una union: usa {expr.name}.campo"
            )
        if log in ctx.array_info:
            if not ctx.array_info[log].array_decay_pointer:
                raise MnemoCompileError(
                    f"l'array {expr.name!r} non è un valore scalare: usa {expr.name}[…]"
                )
        if log in ctx.int_locals:
            return [], Var(_phys(ctx, log)), []
        if expr.name in ctx.enum_constants:
            return [], Imm(ctx.enum_constants[expr.name]), []
        raise MnemoCompileError(f"identificatore non dichiarato: {expr.name!r}")

    if isinstance(expr, c.StructRef):
        if expr.type == "->":
            if not isinstance(expr.name, c.ID) or not isinstance(expr.field, c.ID):
                raise MnemoCompileError("`->`: sintassi non supportata")
            p = _scope_resolve(ctx, expr.name.name)
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
            ei, op, tm = _eval_expr(c.ID(expr.name.name, expr.coord), ctx)
            t_slot = ctx.fresh_temp()
            t_out = ctx.fresh_temp()
            ctx.use_hist = True
            rop: Operand = op if isinstance(op, Imm) else Var(op.name)
            pre = (
                ei
                + [IHistPush(ctx.hist, t_slot), IAddEq(t_slot, rop)]
                + ([IAddEq(t_slot, Imm(off_w))] if off_w != 0 else [])
            )
            ins = pre + _ir_pool_load_call(ctx, t_slot, t_out)
            return ins, Var(t_out), tm + [t_slot, t_out]
        base, path = _structref_base_and_path(expr)
        base_log = _scope_resolve(ctx, base)
        mangled = "__".join(path)
        if base_log in ctx.union_tag_of_var:
            if len(path) != 1:
                raise MnemoCompileError("union: un solo livello di campo")
            field = path[0]
            tag = ctx.union_tag_of_var[base_log]
            spec = ctx.union_specs.get(tag)
            if not spec:
                raise MnemoCompileError(f"union {tag!r}: metadati mancanti")
            fnames = [fn for fn, _ in spec]
            if field not in fnames:
                raise MnemoCompileError(f"union {tag}: membro {field!r} assente")
            if base_log not in ctx.int_locals:
                raise MnemoCompileError(f"union {base!r}: storage mancante")
            return [], Var(_phys(ctx, base_log)), []
        if base_log not in ctx.struct_tag_of_var:
            raise MnemoCompileError(f"{base!r} non è una variabile struct")
        tag = ctx.struct_tag_of_var[base_log]
        spec = ctx.struct_specs.get(tag)
        if not spec:
            raise MnemoCompileError(f"struct {tag!r}: metadati mancanti")
        field_names = [fn for fn, _ in spec]
        if mangled not in field_names:
            raise MnemoCompileError(f"struct {tag}: campo {mangled!r} assente")
        cell = _struct_field_local(base_log, mangled)
        if cell not in ctx.int_locals:
            raise MnemoCompileError(f"campo struct interno mancante: {cell!r}")
        return [], Var(_phys(ctx, cell)), []

    if isinstance(expr, c.ArrayRef):
        # `(*p)[i]`: ArrayRef.name è UnaryOp("*", ID(p)). Equivale a `p[i]`
        # → rewrite a `*(p + i)` (puntatore-indicizzazione).
        nm = expr.name
        if (
            isinstance(nm, c.UnaryOp) and nm.op == "*"
            and isinstance(nm.expr, c.ID)
        ):
            pid = nm.expr
            new_expr = c.UnaryOp(
                "*",
                c.BinaryOp("+", pid, expr.subscript, getattr(expr, "coord", None)),
                getattr(expr, "coord", None),
            )
            return _eval_expr(new_expr, ctx)
        try:
            base, subs = _flatten_array_ref_chain(expr)
        except MnemoCompileError:
            raise
        base_log = _scope_resolve(ctx, base)
        if base_log not in ctx.array_info:
            # Fallback `p[i]` su puntatore: rewrite a `*(p + i)`.
            if (
                base_log in ctx.int_locals
                and isinstance(expr.name, c.ID)
            ):
                new_expr = c.UnaryOp(
                    "*",
                    c.BinaryOp("+", expr.name, expr.subscript,
                               getattr(expr, "coord", None)),
                    getattr(expr, "coord", None),
                )
                return _eval_expr(new_expr, ctx)
            raise MnemoCompileError(
                f"{base!r} non è un array dichiarato (es. int {base}[N] o int {base}[R][C])"
            )
        info = ctx.array_info[base_log]
        if len(subs) != len(info.dims):
            raise MnemoCompileError(
                f"array {base!r}: servono {len(info.dims)} indici, ne ho {len(subs)}"
            )
        coord = getattr(expr, "coord", None)
        if info.array_decay_pointer:
            return _eval_decay_array_elem_read(base_log, subs, info, ctx, coord)
        if all(isinstance(s, c.Constant) for s in subs):
            lin = _const_row_major_linear(subs, info.dims)
            return [], Var(_phys(ctx, _array_elem_local(base_log, lin))), []
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
                IAddEq(t_dest, Var(_phys(ctx, _array_elem_local(base_log, kk)))),
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
        if expr.op == "+":
            # Unary plus: semantica identica all'operando.
            return _eval_expr(expr.expr, ctx)
        if expr.op == "!":
            lc = ctx.fresh_temp()
            t = ctx.fresh_temp()
            # lc diventa 1 se expr e' vera, altrimenti resta 0.
            # Risultato di !expr: 1 - lc.
            ins = [IConst(lc, 0)]
            ins.extend(_build_truth_incr_lc(expr.expr, lc, ctx))
            ins.extend([IConst(t, 1), ISubEq(t, Var(lc))])
            return ins, Var(t), [lc, t]
        if expr.op == "~":
            i0, op0, t0 = _eval_expr(expr.expr, ctx)
            t = ctx.fresh_temp()
            # ~x = (-1) ^ x
            ins = i0 + [ISubEq(t, Imm(1)), IXorEq(t, op0)]
            return ins, Var(t), t0 + [t]
        if expr.op == "-":
            inner = expr.expr
            if isinstance(inner, c.Constant):
                return [], Imm(-_literal_int_widen(inner)), []
            i0, op0, t0 = _eval_expr(inner, ctx)
            t = ctx.fresh_temp()
            ins = i0 + [ISubEq(t, op0)]
            return ins, Var(t), t0 + [t]
        if expr.op == "_Alignof":
            # Mnemo: tutti gli scalari sono word-VM (int=4); alignment di una
            # struct = alignment del campo più "largo", che è sempre uno
            # scalare in Mnemo (no FP/double). Quindi _Alignof(T) = sizeof
            # del MAX scalare = _SIZEOF_SCALAR.
            inner = expr.expr
            if isinstance(inner, c.Typename):
                return [], Imm(_SIZEOF_SCALAR), []
            raise MnemoCompileError(
                "_Alignof: supportato solo su tipo (`_Alignof(T)`)"
            )
        if expr.op == "sizeof":
            inner = expr.expr
            if isinstance(inner, c.Typename):
                return [], Imm(_sizeof_of_c_type_node(inner, ctx)), []
            if isinstance(inner, c.ID):
                log = _scope_resolve(ctx, inner.name)
                if log in ctx.struct_tag_of_var:
                    tag = ctx.struct_tag_of_var[log]
                    return [], Imm(_sizeof_struct_tag(tag, ctx)), []
                if log in ctx.union_tag_of_var:
                    tag = ctx.union_tag_of_var[log]
                    return [], Imm(_sizeof_union_tag(tag, ctx)), []
                if log in ctx.array_info:
                    info = ctx.array_info[log]
                    return [], Imm(info.total * info.elem_size), []
                if log in ctx.array_param_names:
                    return [], Imm(_SIZEOF_POINTER), []
                if log not in ctx.var_types:
                    raise MnemoCompileError(
                        f"sizeof({inner.name}): serve un tipo in (…) o una variabile già dichiarata"
                    )
                return [], Imm(_sizeof_of_c_type_node(ctx.var_types[log], ctx)), []
            if isinstance(inner, c.ArrayRef):
                # `sizeof(a[i])` su array: sizeof(elem). Per pointer-decay (param)
                # ritorna _SIZEOF_POINTER (a[i] è un int via deref, sizeof int).
                try:
                    base, _subs = _flatten_array_ref_chain(inner)
                except MnemoCompileError:
                    base = None
                if base is not None:
                    bl = _scope_resolve(ctx, base)
                    if bl in ctx.array_info:
                        return [], Imm(ctx.array_info[bl].elem_size), []
                    if bl in ctx.array_param_names:
                        return [], Imm(_SIZEOF_SCALAR), []
                return [], Imm(_SIZEOF_SCALAR), []
            if isinstance(inner, c.StructRef):
                # `sizeof(s.field)` o `s->field`: sizeof scalare = _SIZEOF_SCALAR.
                return [], Imm(_SIZEOF_SCALAR), []
            if isinstance(inner, c.UnaryOp) and inner.op == "*":
                # `sizeof(*p)` su puntatore int → 4.
                return [], Imm(_SIZEOF_SCALAR), []
            raise MnemoCompileError(
                "sizeof: supportati solo `sizeof (tipo)`, `sizeof nome_variabile`, "
                "`sizeof a[i]`, `sizeof s.campo`, `sizeof *p`"
            )
        if expr.op == "&":
            inner = expr.expr
            if isinstance(inner, c.ID):
                n = _scope_resolve(ctx, inner.name)
                if n in ctx.array_info:
                    # `&a` su array: indirizzo dell'elemento 0.
                    cell0 = _array_elem_local(n, 0)
                    if cell0 not in ctx.slot_index:
                        raise MnemoCompileError(
                            f"&{inner.name}: array sconosciuto (base non in slot_index)"
                        )
                    ctx.addr_taken_logicals.add(cell0)
                    return [], Imm(ctx.slot_index[cell0]), []
                if n in ctx.slot_index:
                    ctx.addr_taken_logicals.add(n)
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
                            f"&{inner.name}: indirizzo (primo campo) non disponibile"
                        )
                    ctx.addr_taken_logicals.add(cell)
                    return [], Imm(ctx.slot_index[cell]), []
                raise MnemoCompileError(f"&{inner.name}: indirizzo non disponibile")
            if isinstance(inner, c.StructRef) and inner.type == ".":
                base, path = _structref_base_and_path(inner)
                base_log = _scope_resolve(ctx, base)
                mangled = "__".join(path)
                if base_log not in ctx.struct_tag_of_var:
                    raise MnemoCompileError(
                        f"&.{mangled!r}: base non è una variabile struct"
                    )
                cell = _struct_field_local(base_log, mangled)
                if cell not in ctx.slot_index:
                    raise MnemoCompileError(
                        f"&{base}.{mangled}: indirizzo slot non disponibile"
                    )
                ctx.addr_taken_logicals.add(cell)
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
            ins = ei_p + pre_sl + _ir_pool_load_call(ctx, slot_a, t)
            return ins, Var(t), tm_p + tm_sl + [t]
        if expr.op in ("p++", "p--", "++", "--"):
            return _lvalue_inc_dec_prefix_postfix(expr.expr, expr.op, ctx)
        raise MnemoCompileError(f"operatore unario non supportato: {expr.op!r}")

    if isinstance(expr, c.BinaryOp):
        if expr.op in ("&&", "||"):
            lc = ctx.fresh_temp()
            ins = [IConst(lc, 0)]
            ins.extend(_build_truth_incr_lc(expr, lc, ctx))
            return ins, Var(lc), [lc]
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
            pre = pa + pb + [
                ICall(
                    "__mn_mul_into",
                    [t, a_name, b_name] + _kairos_stack_actuals(ctx),
                )
            ]
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
                + [
                    ICall(
                        "__mn_divmod_nonneg",
                        [t_a, vb, t_q, t_r] + _kairos_stack_actuals(ctx),
                    )
                ]
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
                + [
                    ICall(
                        "__mn_mod_nonneg",
                        [t_a, vb, t_r] + _kairos_stack_actuals(ctx),
                    )
                ]
            )
            post = [IHistPush(ctx.scratch, x) for x in reversed(ca + cb + [t_a])]
            ctx.use_hist = True
            ctx.use_scratch = True
            return pre + post, Var(t_r), [t_r]
        if expr.op == "&":
            pa, va, ca = _eval_to_arg_var(expr.left, ctx)
            pb, vb, cb = _eval_to_arg_var(expr.right, ctx)
            t = ctx.fresh_temp()
            pre = pa + pb + [
                ICall("__mn_and_into", [t, va, vb] + _kairos_stack_actuals(ctx))
            ]
            post = [IHistPush(ctx.scratch, x) for x in reversed(ca + cb)]
            if ca or cb:
                ctx.use_scratch = True
            return pre + post, Var(t), [t]
        if expr.op == "|":
            pa, va, ca = _eval_to_arg_var(expr.left, ctx)
            pb, vb, cb = _eval_to_arg_var(expr.right, ctx)
            t = ctx.fresh_temp()
            pre = pa + pb + [
                ICall("__mn_or_into", [t, va, vb] + _kairos_stack_actuals(ctx))
            ]
            post = [IHistPush(ctx.scratch, x) for x in reversed(ca + cb)]
            if ca or cb:
                ctx.use_scratch = True
            return pre + post, Var(t), [t]
        if expr.op == "<<":
            pa, va, ca = _eval_to_arg_var(expr.left, ctx)
            pb, vb, cb = _eval_to_arg_var(expr.right, ctx)
            t = ctx.fresh_temp()
            pre = pa + pb + [
                ICall("__mn_shl_into", [t, va, vb] + _kairos_stack_actuals(ctx))
            ]
            post = [IHistPush(ctx.scratch, x) for x in reversed(ca + cb)]
            if ca or cb:
                ctx.use_scratch = True
            return pre + post, Var(t), [t]
        if expr.op == ">>":
            pa, va, ca = _eval_to_arg_var(expr.left, ctx)
            pb, vb, cb = _eval_to_arg_var(expr.right, ctx)
            t = ctx.fresh_temp()
            pre = pa + pb + [
                ICall("__mn_shr_into", [t, va, vb] + _kairos_stack_actuals(ctx))
            ]
            post = [IHistPush(ctx.scratch, x) for x in reversed(ca + cb)]
            if ca or cb:
                ctx.use_scratch = True
            return pre + post, Var(t), [t]
        raise MnemoCompileError(f"operatore binario non supportato: {expr.op!r}")

    if isinstance(expr, c.Cast):
        if _cast_accepts_pointer_or_scalar(expr, ctx):
            return _eval_expr(expr.expr, ctx)
        raise MnemoCompileError("cast non supportato")

    if isinstance(expr, c.ExprList):
        return _eval_expr(_fold_exprlist_as_comma_chain(expr), ctx)

    if isinstance(expr, c.FuncCall):
        if isinstance(expr.name, c.ID) and expr.name.name == "__mn_offsetof_str":
            return [], Imm(_resolve_offsetof_args(expr, ctx)), []
        if isinstance(expr.name, c.ID) and expr.name.name in ("strlen", "strcmp"):
            res = _try_eval_string_builtin(expr, ctx)
            if res is not None:
                return [], Imm(res), []
        expr, name = _resolve_indirect_callee(expr, ctx)
        if name == "malloc":
            if name not in ctx.extern_procs:
                raise MnemoCompileError(
                    "malloc: dichiarare es. `void *malloc(int n);` o `void *malloc(unsigned n);`"
                )
            if not ctx.proc_returns_int.get(name, False):
                raise MnemoCompileError("malloc deve restituire un puntatore (void* / int*)")
            _register_ptr_pool_locals(ctx)
            t = ctx.fresh_temp()
            ins = [
                ICall(
                    "__mn_pool_alloc",
                    [_PTR_POOL_CTR, t] + _kairos_stack_actuals(ctx),
                )
            ]
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

    if isinstance(expr, c.CompoundLiteral):
        # CompoundLiteral dovrebbe essere hoisted da `_hoist_compound_literals_in_ast`
        # prima di arrivare qui. Se ci arriviamo, è un contesto non gestito dal pre-pass
        # (es. expression annidata dentro nodi non walked).
        raise MnemoCompileError(
            "CompoundLiteral non hoisted (contesto non supportato). "
            "Workaround: dichiara prima un Decl locale (`int tmp[N] = {...};`)."
        )
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
            ainf = ctx.array_info[expr.name]
            if ainf.array_decay_pointer:
                return [], _phys(ctx, expr.name), []
            first = _array_elem_local(expr.name, 0)
            k = ctx.slot_index.get(first)
            if k is None:
                raise MnemoCompileError(
                    f"passaggio array {expr.name!r}: indirizzo base assente nel layout"
                )
            t = ctx.fresh_temp()
            return [IConst(t, k)], t, [t]
        if expr.name not in ctx.int_locals:
            raise MnemoCompileError(f"argomento non dichiarato: {expr.name}")
        return [], _phys(ctx, expr.name), []
    if isinstance(expr, c.Constant):
        if expr.type == "string":
            raise MnemoCompileError(
                "stringa letterale come argomento non supportata (solo in printf)"
            )
        t = ctx.fresh_temp()
        return [IConst(t, _literal_int_widen(expr))], t, [t]
    i, op, tm = _eval_expr(expr, ctx)
    if isinstance(op, Imm):
        t = ctx.fresh_temp()
        return i + [IConst(t, op.value)], t, tm + [t]
    if isinstance(op, Var):
        if op.name not in ctx.int_locals:
            raise MnemoCompileError(f"argomento non dichiarato: {op.name}")
        return i, op.name, tm
    raise MnemoCompileError("argomento chiamata non supportato")


def _lower_mps_init_destroy_inline(
    fname: str, arg0: c.Node, ctx: _Ctx
) -> list[Instr]:
    """
    Espande init_mutexes/destroy_mutexes da mps.h sul chiamante, così i canali mutex
    usano il nome della variabile reale (es. mps, req) e non il parametro formale `m`
    della static inline.
    """
    if not isinstance(arg0, c.UnaryOp) or arg0.op != "&":
        raise MnemoCompileError(f"{fname}: atteso &variabile")
    inner = arg0.expr
    if not isinstance(inner, c.ID):
        raise MnemoCompileError(f"{fname}: atteso &id")
    vid = inner.name
    coord = getattr(arg0, "coord", None)
    pty = ctx.var_types.get(vid)
    if pty is None:
        tag = ctx.struct_tag_of_var.get(vid)
        if tag is None:
            raise MnemoCompileError(f"{fname}: tipo di {vid!r} sconosciuto")
        pl = 0
    else:
        pl = _pointer_level(pty)
        if pl >= 1:
            tag = _pointee_struct_tag(pty, ctx)
        else:
            tag = _struct_tag_for_decl_type(pty, ctx)
        if tag is None:
            raise MnemoCompileError(f"{fname}: {vid!r} non è struct mps / puntatore a struct")
    spec = ctx.struct_specs.get(tag)
    if not spec:
        raise MnemoCompileError(f"{fname}: struct {tag!r} senza metadati")
    fields = {fn: ft for fn, ft in spec}
    if "lane" not in fields or not _type_node_is_pthread_mutex(
        fields["lane"], ctx.typedef_map
    ):
        raise MnemoCompileError(
            f"{fname}: serve campo pthread_mutex_t `lane` su {tag} (mps_t single-channel)"
        )

    def mref(fld: str) -> c.Node:
        if pl >= 1:
            return c.UnaryOp(
                "&",
                c.StructRef(c.ID(vid, coord), "->", c.ID(fld, coord), coord),
                coord,
            )
        return c.UnaryOp(
            "&",
            c.StructRef(c.ID(vid, coord), ".", c.ID(fld, coord), coord),
            coord,
        )

    def emit_pthread_mnemo(fc: c.FuncCall) -> None:
        ins = _lower_pthread_mnemo_call(fc, ctx)
        if ins is None:
            raise MnemoCompileError(f"{fname}: atteso intrinseco pthread/π")
        out.extend(ins)

    out: list[Instr] = []
    if fname == "init_mutexes":
        # FIFO channel (__mn_kch_*): nessun token iniziale (bloccherebbe ssend in main).
        return out
    if fname == "destroy_mutexes":
        # Single-channel mps: dopo l'ultimo srecv il canale è vuoto, niente da drenare.
        return out
    raise MnemoCompileError(f"funzione non supportata per inline mutex: {fname}")


def _mps_channel_ptr_id(ch: c.Node) -> c.ID:
    if isinstance(ch, c.ID):
        return ch
    raise MnemoCompileError("mps_t*: atteso un identificatore (puntatore al canale)")


def _mps_lane_channel_name(cid: c.ID, ctx: _Ctx) -> str:
    """Risolve il canale Kairos del campo `lane` di mps_t (`__mn_mtx_<base>__<tag>__lane`)."""
    coord = getattr(cid, "coord", None)
    lane_ref = c.UnaryOp(
        "&",
        c.StructRef(cid, "->", c.ID("lane", coord), coord),
        coord,
    )
    key = _pthread_mutex_channel_key(lane_ref, ctx)
    return ctx.channel_kairos[key]


def _lower_mps_ssend_inline(ch: c.Node, msg: c.Node, ctx: _Ctx) -> list[Instr]:
    """Singolo Kairos `ssend(<tmp>, lane)` (mps_t a singolo canale).
    ssend consuma il payload (Janus): copia `msg` in un fresh temp e poi
    `ssend(<temp>, lane)` lo azzera. Niente accumulo cross-iter perché ssend
    consuma il temp.
    """
    cid = _mps_channel_ptr_id(ch)
    chname = _mps_lane_channel_name(cid, ctx)
    ei, op, tm = _eval_expr(msg, ctx)
    out: list[Instr] = list(ei)
    t_send = ctx.fresh_temp()
    if isinstance(op, Imm):
        out.append(IConst(t_send, op.value))
    else:
        ctx.use_hist = True
        out.append(IHistPush(ctx.hist, t_send))
        out.append(IAddEq(t_send, op))
    out.append(ISsend(chname, [t_send]))  # consuma t_send → 0
    if tm:
        ctx.use_scratch = True
    for tmp in reversed(tm):
        out.append(IHistPush(ctx.scratch, tmp))
    return out


def _lower_mps_srecv_inline(ch: c.Node, ans_ptr: c.Node, ctx: _Ctx) -> list[Instr]:
    """Singolo Kairos `srecv(<dst>, lane)` (mps_t a singolo canale).
    Per `int *p` (puntatore): srecv in fresh temp, deref-assign in `*p`
    (pool_store), poi `push(t, hist)` per azzerare il temp prima del prossimo
    statement / del proc-end delocal. Senza la push finale, ogni iter di un
    loop lascia il temp = recv_val → DELOCAL valore errato e inverse buggy.
    """
    cid = _mps_channel_ptr_id(ch)
    chname = _mps_lane_channel_name(cid, ctx)
    coord = getattr(ans_ptr, "coord", None)
    if isinstance(ans_ptr, c.UnaryOp) and ans_ptr.op == "&" and isinstance(
        ans_ptr.expr, c.ID
    ):
        dest = _phys(ctx, ans_ptr.expr.name)
        return [ISrecv([dest], chname)]
    if isinstance(ans_ptr, c.ID):
        t_recv = ctx.fresh_temp()
        out: list[Instr] = [ISrecv([t_recv], chname)]
        out.extend(_lower_deref_assign(ans_ptr.name, c.ID(t_recv, coord), ctx))
        # Azzeramento per-iter: senza questa push, in un loop ogni srecv
        # accumula nel t_recv (semantica Kairos `srecv <dst>, ch` è `dst += msg`).
        # PC.c: consumer riceveva 0,1,2,3,... ma stampava 0,1,3,6,10 (triangolari)
        # perché t_recv non veniva azzerato tra iter.
        ctx.use_scratch = True
        out.append(IHistPush(ctx.scratch, t_recv))
        return out
    raise MnemoCompileError(
        "srecv: secondo argomento atteso `&msg` o `int *p` (forma semplice)"
    )


def _resolve_pi_channel_endpoint(expr: c.Node, ctx: _Ctx) -> str:
    """`&c` con `c` dichiarato `mnemo_kairos_channel_t` → nome formale channel Kairos."""
    if isinstance(expr, c.UnaryOp) and expr.op == "&" and isinstance(expr.expr, c.ID):
        n = expr.expr.name
        if n in ctx.channel_kairos:
            return ctx.channel_kairos[n]
    raise MnemoCompileError(
        "mnemo_pi_*: atteso `&nome` con `nome` di tipo mnemo_kairos_channel_t"
    )


_UNCALL_UNSAFE_LIB_PROCS = frozenset()


def _instr_list_uncall_unsafe_via_vm(instrs: list[Instr]) -> bool:
    """
    True se il callee contiene costrutti che l'inversore Kairos non deve elidere in
    `call`+`uncall` SINGOLO (PAR nested, lib unsafe). Ssend/srecv NON sono qui
    perché compatibili con par-uncall (inversi simmetrici si parlano); per single
    call site usare `_instr_list_uncall_unsafe_outside_par`.
    """

    def rec(seq: list[Instr]) -> bool:
        for ins in seq:
            if isinstance(ins, IPar):
                if any(rec(br) for br in ins.branches):
                    return True
            elif isinstance(ins, IIfKairos):
                if rec(ins.then_instrs):
                    return True
                if ins.else_instrs is not None and rec(ins.else_instrs):
                    return True
            elif isinstance(ins, IFromUntilKairos):
                if rec(ins.body_instrs):
                    return True
            elif isinstance(ins, ILocalBlock):
                if rec(ins.body_instrs):
                    return True
            elif isinstance(ins, ICall) and ins.proc in _UNCALL_UNSAFE_LIB_PROCS:
                return True
        return False

    return rec(instrs)


def _instr_list_uses_channels(instrs: list[Instr]) -> bool:
    """True se il callee usa ssend/srecv. Compatibile con par-uncall ma non con
    single-call opt-uncall (l'inverse srecv resterebbe in attesa senza counterpart)."""

    def rec(seq: list[Instr]) -> bool:
        for ins in seq:
            if isinstance(ins, IPar):
                if any(rec(br) for br in ins.branches):
                    return True
            elif isinstance(ins, IIfKairos):
                if rec(ins.then_instrs):
                    return True
                if ins.else_instrs is not None and rec(ins.else_instrs):
                    return True
            elif isinstance(ins, IFromUntilKairos):
                if rec(ins.body_instrs):
                    return True
            elif isinstance(ins, ILocalBlock):
                if rec(ins.body_instrs):
                    return True
            elif isinstance(ins, (ISsend, ISrecv)):
                return True
        return False

    return rec(instrs)


def _user_procedure_uses_channels(fn: Function) -> bool:
    return any(_instr_list_uses_channels(b.instrs) for b in fn.blocks)


def _user_procedure_uncall_excluded_via_vm(fn: Function) -> bool:
    """True ⇒ non applicare --opt-uncall-user-calls alle chiamate verso fn."""
    return any(
        _instr_list_uncall_unsafe_via_vm(b.instrs) for b in fn.blocks
    )


def _function_ir_calls_proc_in(fn: Function, names: set[str]) -> bool:
    """True se il corpo IR contiene un ICall verso una delle `names`."""

    def rec(seq: list[Instr]) -> bool:
        for ins in seq:
            if isinstance(ins, IPar):
                if any(rec(br) for br in ins.branches):
                    return True
            elif isinstance(ins, IIfKairos):
                if rec(ins.then_instrs):
                    return True
                if ins.else_instrs is not None and rec(ins.else_instrs):
                    return True
            elif isinstance(ins, IFromUntilKairos):
                if rec(ins.body_instrs):
                    return True
            elif isinstance(ins, ILocalBlock):
                if rec(ins.body_instrs):
                    return True
            elif isinstance(ins, ICall):
                if ins.proc in names:
                    return True
        return False

    return any(rec(b.instrs) for b in fn.blocks)


_MEM_NAME_PREFIX = "__mn_mem"


def _mem_idx_or_none(name: str | None) -> int | None:
    if not name or not name.startswith(_MEM_NAME_PREFIX):
        return None
    suf = name[len(_MEM_NAME_PREFIX):]
    if not suf.isdigit():
        return None
    return int(suf)


def _collect_mem_refs_from_seq(seq: list[Any]) -> tuple[set[int], list[tuple[str, list[str]]]]:
    """Restituisce (mem indices direttamente referenziati, [(callee, args)] di ICall/IUncall)."""
    refs: set[int] = set()
    calls: list[tuple[str, list[str]]] = []

    def add(n: str | None) -> None:
        i = _mem_idx_or_none(n)
        if i is not None:
            refs.add(i)

    def add_operand(o: Any) -> None:
        if isinstance(o, Var):
            add(o.name)
        elif isinstance(o, str):
            add(o)

    def rec(ss: list[Any]) -> None:
        for ins in ss:
            if isinstance(ins, IConst):
                add(ins.dst)
            elif isinstance(ins, (IAddEq, ISubEq, IXorEq)):
                add(ins.dst); add_operand(ins.rhs)
            elif isinstance(ins, IHistPush):
                add(ins.var)
            elif isinstance(ins, (ICall, IUncall)):
                calls.append((ins.proc, list(ins.args)))
            elif isinstance(ins, IShow):
                add(ins.var)
            elif isinstance(ins, IIfKairos):
                add(ins.lhs); add(ins.rhs)
                rec(ins.then_instrs)
                if ins.else_instrs is not None:
                    rec(ins.else_instrs)
            elif isinstance(ins, IFromUntilKairos):
                add(ins.entry_lhs); add(ins.entry_rhs)
                add(ins.until_lhs); add(ins.until_rhs)
                rec(ins.body_instrs)
            elif isinstance(ins, ILocalBlock):
                add(ins.var)
                rec(ins.body_instrs)
            elif isinstance(ins, IPar):
                for br in ins.branches:
                    rec(br)
            elif isinstance(ins, ISsend):
                for a in ins.payload_atoms:
                    add(a)
            elif isinstance(ins, ISrecv):
                for d in ins.dests:
                    add(d)
    rec(seq)
    return refs, calls


def _function_direct_mem_touches(fn: Function) -> tuple[set[int], list[tuple[str, list[str]]]]:
    refs: set[int] = set()
    calls: list[tuple[str, list[str]]] = []
    for b in fn.blocks:
        r, c_ = _collect_mem_refs_from_seq(b.instrs)
        refs |= r
        calls.extend(c_)
    return refs, calls


def _compute_callee_mem_touches(
    probe_map: dict[str, Function],
    total_cells: int,
) -> dict[str, frozenset[int]]:
    """Per ogni user fn, set di indici `__mn_mem<i>` che il body (incluse callee) può toccare.

    Chiusura a punto-fisso. Per callee non-user (lib, builtin), assume tutti i mem cell args
    toccati (conservativo). Mappa posizionale: callee touched index `j` → caller's arg<j>.
    """
    direct: dict[str, set[int]] = {}
    calls: dict[str, list[tuple[str, list[str]]]] = {}
    for n, fn in probe_map.items():
        d, c_ = _function_direct_mem_touches(fn)
        direct[n] = d
        calls[n] = c_

    touched: dict[str, set[int]] = {n: set(direct[n]) for n in probe_map}
    changed = True
    while changed:
        changed = False
        for n in probe_map:
            for callee, args in calls[n]:
                arg_mem: list[int | None] = [_mem_idx_or_none(a) for a in args]
                if callee in probe_map:
                    callee_t = touched[callee]
                    for j in callee_t:
                        if j < len(arg_mem) and arg_mem[j] is not None:
                            ci = arg_mem[j]
                            assert ci is not None
                            if ci not in touched[n]:
                                touched[n].add(ci)
                                changed = True
                else:
                    for ai in arg_mem:
                        if ai is not None and ai not in touched[n]:
                            touched[n].add(ai)
                            changed = True
    return {n: frozenset(s) for n, s in touched.items()}


def _uncall_excluded_transitive_closure(probe_map: dict[str, Function]) -> frozenset[str]:
    """
    Chiusura: direttamente unsafe (pool, par, …) oppure che chiama una funzione già
    esclusa. Lo XOR ottimizzato su tutte le __mn_mem* non commuta con callees esclusi.
    """
    blocked: set[str] = {
        n for n, f in probe_map.items() if _user_procedure_uncall_excluded_via_vm(f)
    }
    changed = True
    while changed:
        changed = False
        for n, f in probe_map.items():
            if n in blocked:
                continue
            if _function_ir_calls_proc_in(f, blocked):
                blocked.add(n)
                changed = True
    return frozenset(blocked)


def _resolve_pi_int_recv_dest(expr: c.Node, ctx: _Ctx) -> str:
    if isinstance(expr, c.UnaryOp) and expr.op == "&" and isinstance(expr.expr, c.ID):
        return _phys(ctx, expr.expr.name)
    raise MnemoCompileError("mnemo_pi_*: atteso `&int` come destinazione di lettura")


def _lower_funccall_with_ret(
    node: c.FuncCall, ctx: _Ctx, ret_sink: str | list[str] | None
) -> list[Instr]:
    node, name = _resolve_indirect_callee(node, ctx)
    assert isinstance(node.name, c.ID)
    if name == "putchar":
        if ret_sink is not None:
            raise MnemoCompileError("putchar è void")
        el = node.args
        exprs = list(el.exprs) if el is not None else []
        if len(exprs) != 1:
            raise MnemoCompileError("putchar richiede esattamente un argomento")
        return _lower_putchar(exprs[0], ctx)
    if name == "printf":
        if ret_sink is not None:
            raise MnemoCompileError("printf è void")
        return _lower_printf(node, ctx)
    if name == "puts":
        # `puts(s)` = `printf("...\n")` per letterale o `printf("%s\n", s)`
        # per ID. Mnemo non supporta full POSIX puts (return int = !EOF), ma
        # `puts` come void è ampiamente usato per debug — coperto qui.
        if ret_sink is not None:
            raise MnemoCompileError("puts: valore di ritorno non supportato (usa come void)")
        el = node.args
        exprs = list(el.exprs) if el is not None else []
        if len(exprs) != 1:
            raise MnemoCompileError("puts: atteso 1 argomento")
        arg = exprs[0]
        coord = node.coord
        if isinstance(arg, c.Constant) and arg.type == "string":
            raw = _literal_c_string(arg)
            fmt_node = c.Constant("string", '"' + raw.replace("\\", "\\\\").replace('"', '\\"') + '\\n"', coord)
            synth = c.FuncCall(c.ID("printf", coord), c.ExprList([fmt_node], coord), coord)
            return _lower_printf(synth, ctx)
        # Non-literal: usa printf("%s\n", arg)
        fmt_node = c.Constant("string", '"%s\\n"', coord)
        synth = c.FuncCall(c.ID("printf", coord), c.ExprList([fmt_node, arg], coord), coord)
        return _lower_printf(synth, ctx)
    if name in ("init_mutexes", "destroy_mutexes"):
        if ret_sink is not None:
            raise MnemoCompileError(f"{name} è void")
        el = node.args
        exprs = list(el.exprs) if el is not None else []
        if len(exprs) != 1:
            raise MnemoCompileError(f"{name}: atteso un argomento")
        if ctx.mem_layout is None:
            raise MnemoCompileError(f"{name}: contesto senza layout memoria")
        return _lower_mps_init_destroy_inline(name, exprs[0], ctx)
    if name == "ssend":
        if ret_sink is not None:
            raise MnemoCompileError("ssend è void")
        el = node.args
        exprs = list(el.exprs) if el is not None else []
        if len(exprs) != 2:
            raise MnemoCompileError("ssend: attesi 2 argomenti")
        if ctx.mem_layout is None:
            raise MnemoCompileError("ssend: contesto senza layout memoria")
        return _lower_mps_ssend_inline(exprs[0], exprs[1], ctx)
    if name == "srecv":
        if ret_sink is not None:
            raise MnemoCompileError("srecv è void")
        el = node.args
        exprs = list(el.exprs) if el is not None else []
        if len(exprs) != 2:
            raise MnemoCompileError("srecv: attesi 2 argomenti")
        if ctx.mem_layout is None:
            raise MnemoCompileError("srecv: contesto senza layout memoria")
        return _lower_mps_srecv_inline(exprs[0], exprs[1], ctx)
    if name in MNEMO_PI_KAIROS_INTRINSICS:
        if ret_sink is not None:
            raise MnemoCompileError(f"{name} è void")
        el = node.args
        exprs = list(el.exprs) if el is not None else []
        ctx.use_hist = True
        if name == "mnemo_pi_ssend_request":
            if len(exprs) != 3:
                raise MnemoCompileError(
                    "mnemo_pi_ssend_request: attesi (lane, msg, &return_channel)"
                )
            lane = _resolve_pi_channel_endpoint(exprs[0], ctx)
            pre, atom, tm = _kairos_atom(exprs[1], ctx)
            reply = _resolve_pi_channel_endpoint(exprs[2], ctx)
            post: list[Instr] = []
            if tm:
                ctx.use_scratch = True
                post.extend([IHistPush(ctx.scratch, x) for x in reversed(tm)])
            return pre + [ISsend(lane, [atom, reply])] + post
        if name == "mnemo_pi_srecv_request":
            if len(exprs) != 3:
                raise MnemoCompileError(
                    "mnemo_pi_srecv_request: attesi (lane, &msg, &return_channel)"
                )
            lane = _resolve_pi_channel_endpoint(exprs[0], ctx)
            msg_d = _resolve_pi_int_recv_dest(exprs[1], ctx)
            rp_d = _resolve_pi_channel_endpoint(exprs[2], ctx)
            return [ISrecv([msg_d, rp_d], lane)]
        if name == "mnemo_pi_ssend_reply":
            if len(exprs) != 2:
                raise MnemoCompileError("mnemo_pi_ssend_reply: attesi 2 argomenti")
            lane = _resolve_pi_channel_endpoint(exprs[0], ctx)
            # ssend richiede un identificatore (no letterali): materializza in fresh temp
            # se il payload è una costante o un'espressione.
            pre, atom, tm = _eval_to_var(exprs[1], ctx)
            post2: list[Instr] = []
            if tm:
                ctx.use_scratch = True
                post2.extend([IHistPush(ctx.scratch, x) for x in reversed(tm)])
            return pre + [ISsend(lane, [atom])] + post2
        if name == "mnemo_pi_srecv_reply":
            if len(exprs) != 2:
                raise MnemoCompileError("mnemo_pi_srecv_reply: attesi 2 argomenti")
            lane = _resolve_pi_channel_endpoint(exprs[0], ctx)
            msg_d = _resolve_pi_int_recv_dest(exprs[1], ctx)
            return [ISrecv([msg_d], lane)]
        raise MnemoCompileError(f"intrinseco π non gestito: {name}")
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
            orig_exprs = list(exprs)
            fg: list[list[str]] = []
            fr: list[c.Node] = []
            for g, e in zip(groups, orig_exprs):
                if _func_param_group_is_pi_channel(g, callee_fd, ctx.typedef_map):
                    continue
                fg.append(g)
                fr.append(e)
            lead_arg, exprs = _flatten_user_call_arguments(fr, fg, ctx, layout)
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
            _ct_callee = ctx.callee_mem_touches.get(name)
            if _ct_callee is None:
                mem_args = [f"__mn_mem{i}" for i in range(layout.total_cells)]
            else:
                mem_args = [f"__mn_mem{i}" for i in sorted(_ct_callee)]
            pi_suffix = _call_pi_channel_kairos_names(callee_fd, orig_exprs, ctx)
            ctx.use_hist = True
            chx = _file_scope_channel_actuals(ctx)
            stk = _kairos_stack_actuals(ctx)
            ir_blk = name in ctx.uncall_excluded_via_vm_targets
            ch_blk = name in ctx.channel_using_targets
            self_rec = (name == ctx.fn_name)
            in_par2_worker = ctx.fn_name in ctx.par2_workers
            apply_uncall_opt = (
                ctx.opt_uncall_user_calls
                and wants
                and ret_sink is not None
                and rw_c >= 1
                and not self_rec
                and not ir_blk
                and not ch_blk
                and not in_par2_worker
            )
            apply_void_uncall_opt = (
                ctx.opt_uncall_user_calls
                and not wants
                and ret_sink is None
                and rw_c == 0
                and not self_rec
                and not ir_blk
                and not ch_blk
                and not in_par2_worker
            )
            uncall_with_restore: list[Instr] = []
            snap_pairs: list[tuple[int, str]] = []
            if apply_uncall_opt or apply_void_uncall_opt:
                touched = ctx.callee_mem_touches.get(name)
                if touched is None:
                    cell_iter = list(range(layout.total_cells))
                else:
                    cell_iter = sorted(i for i in touched if i < layout.total_cells)
                for kk in cell_iter:
                    t_cell = ctx.fresh_temp()
                    snap_pairs.append((kk, t_cell))
                    uncall_with_restore.append(IXorEq(t_cell, Var(f"__mn_mem{kk}")))
                uncall_with_restore.append(
                    IUncall(name, mem_args + pi_suffix + chx + stk)
                )
                for kk, t_cell in snap_pairs:
                    mk = f"__mn_mem{kk}"
                    v_m = Var(mk)
                    v_t = Var(t_cell)
                    uncall_with_restore.extend(
                        [
                            IXorEq(mk, v_t),
                            IXorEq(t_cell, v_m),
                            IXorEq(mk, v_t),
                        ]
                    )
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
                    src_id = f"__mn_mem{ri}"
                    post_uc.extend(_lower_assign(ret_sink, c.ID(src_id, coord), ctx))
                else:
                    if len(ret_sink) != rw_c:
                        raise MnemoCompileError(
                            f"{name}: servono {rw_c} slot di ritorno, "
                            f"ne ho {len(ret_sink)}"
                        )
                    for dst, rn in zip(ret_sink, rnames):
                        ri = layout.slot_of[(name, rn)]
                        src_id = f"__mn_mem{ri}"
                        post_uc.extend(_lower_assign(dst, c.ID(src_id, coord), ctx))
            call_uc: list[Instr] = []
            if apply_uncall_opt or apply_void_uncall_opt:
                call_uc.append(ICall("__mn_hist_floor_snap", [ctx.hist]))
            call_uc.append(ICall(name, mem_args + pi_suffix + chx + stk))
            if apply_uncall_opt or apply_void_uncall_opt:
                call_uc.extend(uncall_with_restore)
            return pre_uc + call_uc + post_uc

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
        return pre + pre_al + _ir_pool_free_call(ctx, free_slot) + post + post_al
    if wants:
        if ret_sink is None or not isinstance(ret_sink, str):
            raise MnemoCompileError(
                f"{name} restituisce un valore: uso interno errato (sink)"
            )
        arg_names.append(ret_sink)
    if to_clear:
        ctx.use_scratch = True
    post = [IHistPush(ctx.scratch, t) for t in reversed(to_clear)]
    return pre + [ICall(name, arg_names + _kairos_stack_actuals(ctx))] + post


def _lower_return_aggregate(expr: c.Node, ctx: _Ctx) -> list[Instr]:
    """return con tipo struct su più parole (__mn_ret0, …)."""
    rw = len(ctx.ret_vars)
    if rw < 2:
        raise MnemoCompileError("return aggregato: errore interno")
    if isinstance(expr, c.FuncCall):
        norm_ret, callee = _resolve_indirect_callee(expr, ctx)
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
        return _lower_funccall_with_ret(norm_ret, ctx, list(ctx.ret_vars)) + [IReturn()]
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
        ins, _opv, tm = _lvalue_inc_dec_prefix_postfix(expr.expr, expr.op, ctx)
        ctx.use_hist = True
        out = list(ins)
        fin = list(tm)
        if fin:
            ctx.use_scratch = True
        out.extend([IHistPush(ctx.scratch, x) for x in reversed(fin)])
        return out
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
    pl = _scope_resolve(ctx, p)
    if pl not in ctx.int_locals:
        raise MnemoCompileError(f"puntatore non dichiarato: {p!r}")
    pty = ctx.var_types.get(pl)
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
        + _ir_pool_store_call(ctx, slot_a, val)
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
    ins = pre + pre_slot + _ir_pool_store_call(ctx, slot_a, val)
    post = [IHistPush(ctx.scratch, x) for x in reversed(temps + tm_sl)]
    return ins + post


def _lower_assign(lhs: str, rhs: c.Node, ctx: _Ctx) -> list[Instr]:
    if isinstance(rhs, c.ID):
        rlog = _scope_resolve(ctx, rhs.name)
        if rlog in ctx.array_info:
            ainf = ctx.array_info[rlog]
        else:
            ainf = None
    else:
        ainf = None
    if ainf is not None and isinstance(rhs, c.ID) and not ainf.array_decay_pointer:
        first = _array_elem_local(rlog, 0)
        k = ctx.slot_index.get(first)
        if k is None:
            raise MnemoCompileError(
                f"array {rhs.name!r}: indirizzo base assente nel layout"
            )
        ctx.use_hist = True
        return [IHistPush(ctx.hist, lhs), IAddEq(lhs, Imm(k))]
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
    blog = _scope_resolve(ctx, base)
    if blog not in ctx.array_info:
        raise MnemoCompileError(f"array {base!r} non dichiarato")
    info = ctx.array_info[blog]
    if len(subs) != len(info.dims):
        raise MnemoCompileError(
            f"array {base!r}: servono {len(info.dims)} indici nell'lvalue"
        )
    if info.array_decay_pointer:
        return _lower_decay_array_subscript_assign(blog, subs, rhs, info, ctx)
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
        cell = _array_elem_local(blog, lin)
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
            IHistPush(ctx.hist, _phys(ctx, _array_elem_local(blog, kk))),
            IAddEq(_phys(ctx, _array_elem_local(blog, kk)), Var(val)),
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
        v = _literal_int_widen(expr)
        if v < 0:
            t = ctx.fresh_temp()
            return [ISubEq(t, Imm(-v))], t, [t]
        return [], str(v), []
    if isinstance(expr, c.UnaryOp) and expr.op == "-" and isinstance(
        expr.expr, c.Constant
    ):
        v = -_literal_int_widen(expr.expr)
        if v < 0:
            t = ctx.fresh_temp()
            return [ISubEq(t, Imm(-v))], t, [t]
        return [], str(v), []
    if isinstance(expr, c.ID):
        log = _scope_resolve(ctx, expr.name)
        if log in ctx.int_locals:
            return [], _phys(ctx, log), []
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
        log = _scope_resolve(ctx, expr.name)
        if log in ctx.int_locals:
            return [], (_phys(ctx, log), "!=", "0"), []
        if expr.name in ctx.enum_constants:
            v = ctx.enum_constants[expr.name]
            if v == 0:
                return [], ("0", "==", "1"), []
            return [], ("0", "==", "0"), []
        raise MnemoCompileError(f"condizione: variabile non dichiarata {expr.name!r}")
    if isinstance(expr, c.Constant):
        v = _literal_int_widen(expr)
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


def _truth_lc_keep(ctx: _Ctx, lc: str) -> list[Instr]:
    """
    Ramo else bilanciato rispetto a _truth_lc_incr: sempre push(lc, hist) e add 0 su lc,
    così invertendo la VM non deve distinguere dal then che aveva lc+=1 dopo lo stesso push.
    """

    ctx.use_hist = True
    return [IHistPush(ctx.hist, lc), IAddEq(lc, Imm(0))]


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
    out: list[Instr] = pre + [
        IIfKairos(
            lh,
            op,
            rh,
            _truth_lc_incr(ctx, lc),
            _truth_lc_keep(ctx, lc),
        )
    ]
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


def _is_break_only_stmt(stmt: c.Node | None) -> bool:
    if stmt is None:
        return False
    if isinstance(stmt, c.Break):
        return True
    if isinstance(stmt, c.Compound):
        items = stmt.block_items or []
        return len(items) == 1 and _is_break_only_stmt(items[0])
    return False


def _if_break_only(node: c.If) -> bool:
    return _is_break_only_stmt(node.iftrue) and node.iffalse is None


def _lower_stmt_list_tail_continue(
    stmts: list[c.Node], ctx: _Ctx, ct_var: str | None
) -> list[Instr]:
    if not stmts:
        return []
    # Pick up the loop's br_var (if any) from the loop stack — used to gate
    # the tail of the body after a `break` (or `if (cond) break`) in the
    # middle of the iteration.
    br_var: str | None = (
        ctx.loop_stack[-1].br_var if ctx.loop_stack else None
    )
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
        if isinstance(s, c.Break):
            if br_var is None:
                raise MnemoCompileError(
                    "break fuori da loop (o break in switch annidato senza loop)"
                )
            head = _lower_stmt_list_tail_continue(stmts[:i], ctx, ct_var)
            ctx.use_hist = True
            inc = [IHistPush(ctx.hist, br_var), IAddEq(br_var, Imm(1))]
            return head + inc
        if isinstance(s, c.If) and _if_break_only(s):
            if br_var is None:
                raise MnemoCompileError(
                    "break fuori da loop (o break in switch annidato senza loop)"
                )
            head = _lower_stmt_list_tail_continue(stmts[:i], ctx, ct_var)
            tail = _lower_stmt_list_tail_continue(stmts[i + 1 :], ctx, ct_var)
            ctx.use_hist = True
            inc = [IHistPush(ctx.hist, br_var), IAddEq(br_var, Imm(1))]
            branch = _lower_if_from_expr(s.cond, inc, None, ctx)
            gated = [IIfKairos(br_var, "==", "0", tail, None)] if tail else []
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


def _build_counter_loop_instrs(
    orig_body: list[Instr],
    init_lc: str,
    exit_lhs: str,
    exit_op: CmpOp,
    exit_rhs: str,
    ctx: _Ctx,
    needs_entry_guard: bool,
) -> list[Instr]:
    """Wrappa loop con counter `cnt` (entry `from cnt == 0`) per VM heuristic.

    Entry guard `from cnt == 0` matcha `loop_entry_eq_zero_guard` (vm_invert.h:414):
    in inverse il numero di peel = cnt corrente → evita heuristic deep_peel rotta
    su loop generici. Body finale: `cnt += 1`.

    Per loop con 0 iter (es. `for(i; i<0; i++)`) `from cnt == 0` esegue body una
    "skip-iter" → semantica != C. Quando `needs_entry_guard=True` wrappiamo il
    counter-loop in IIfKairos `g != 0` con g=snapshot di init_lc (lc è 1 se cond
    iniziale vera, 0 altrimenti). g resta invariato dentro IF → exit assert
    `g != 0` distingue THEN da ELSE per inverse Janus. Push(g, hist) + delocal
    chiudono lifecycle. Skip wrap quando init_lc == exit_lhs e `needs_entry_guard`
    è False (dowhile: body always runs almeno 1 volta per semantica C).
    """
    cnt = ctx.fresh_loop_ct()
    ctx.use_hist = True
    body_with_cnt = orig_body + [IAddEq(cnt, Imm(1))]
    loop_block = [ILocalBlock(cnt, [
        IFromUntilKairos(cnt, "==", "0", body_with_cnt, exit_lhs, exit_op, exit_rhs),
        IHistPush("__mn_hist", cnt),
    ])]
    if not needs_entry_guard:
        return loop_block
    g = ctx.fresh_loop_ct()
    return [ILocalBlock(g, [
        IAddEq(g, Var(init_lc)),
        IIfKairos(g, "!=", "0", loop_block),
        IHistPush("__mn_hist", g),
    ])]


def _lower_next_clause(node: c.Node | None, ctx: _Ctx) -> list[Instr]:
    if node is None:
        return []
    if getattr(c, "ExprStmt", None) is not None and isinstance(node, c.ExprStmt):
        if node.expr is None:
            return []
        return _lower_expr_as_stmt(node.expr, ctx)
    if isinstance(node, c.ExprList):
        # `for (...; ...; i+=1, j-=1)`: ogni stmt in sequenza.
        out: list[Instr] = []
        for e in node.exprs:
            out.extend(_lower_expr_as_stmt(e, ctx))
        return out
    return _lower_expr_as_stmt(node, ctx)


def _lower_while(node: c.While, ctx: _Ctx) -> list[Instr]:
    lc = ctx.fresh_temp()
    cond = node.cond if node.cond is not None else c.Constant("int", "1")
    noop_ct = _loop_body_continue_is_noop(node.stmt)
    body_scope = not noop_ct and isinstance(node.stmt, c.Compound)
    stmts = (
        []
        if noop_ct
        else (
            list(node.stmt.block_items or [])
            if isinstance(node.stmt, c.Compound)
            else [node.stmt]
        )
    )
    need_br = _has_break_targeting_loop(node.stmt, False)
    need_ct = _has_continue_targeting_loop(node.stmt, False) and not noop_ct
    br_v = ctx.fresh_loop_ct() if need_br else None
    ct_v = ctx.fresh_loop_ct() if need_ct else None

    ctx.loop_stack.append(_LoopFrame(br_v, ct_v))
    try:
        if body_scope:
            _scope_enter(ctx)
            try:
                core = _lower_stmt_list_tail_continue(stmts, ctx, ct_v)
            finally:
                _scope_exit(ctx)
        else:
            core = _lower_stmt_list_tail_continue(stmts, ctx, ct_v)
        if need_ct:
            assert ct_v is not None
            core = [ILocalBlock(ct_v, core + _reset_lc_val(ct_v, ctx))]
        recompute = _reset_lc_val(lc, ctx) + _build_truth_incr_lc_br(cond, lc, ctx, br_v)
        body = core + recompute
    finally:
        ctx.loop_stack.pop()

    first_eval = _build_truth_incr_lc_br(cond, lc, ctx, br_v)
    loop_instrs = first_eval + _build_counter_loop_instrs(
        body, lc, lc, "==", "0", ctx, needs_entry_guard=True
    )
    if need_br:
        assert br_v is not None
        # Wrap loop in ILocalBlock(br_v): isolates per-invocation; senza
        # questo wrap, br_v resterebbe a 1 dopo un break, e una eventuale
        # ri-esecuzione del while (es. annidato in for esterno) salterebbe
        # tutte le iterazioni.
        loop_instrs = [ILocalBlock(br_v, loop_instrs + _reset_lc_val(br_v, ctx))]
    return loop_instrs


def _lower_dowhile(node: c.DoWhile, ctx: _Ctx) -> list[Instr]:
    lc = ctx.fresh_temp()
    cond = node.cond if node.cond is not None else c.Constant("int", "1")
    noop_ct = _loop_body_continue_is_noop(node.stmt)
    body_scope = not noop_ct and isinstance(node.stmt, c.Compound)
    stmts = (
        []
        if noop_ct
        else (
            list(node.stmt.block_items or [])
            if isinstance(node.stmt, c.Compound)
            else [node.stmt]
        )
    )
    need_br = _has_break_targeting_loop(node.stmt, False)
    need_ct = _has_continue_targeting_loop(node.stmt, False) and not noop_ct
    br_v = ctx.fresh_loop_ct() if need_br else None
    ct_v = ctx.fresh_loop_ct() if need_ct else None

    ctx.loop_stack.append(_LoopFrame(br_v, ct_v))
    try:
        if body_scope:
            _scope_enter(ctx)
            try:
                core = _lower_stmt_list_tail_continue(stmts, ctx, ct_v)
            finally:
                _scope_exit(ctx)
        else:
            core = _lower_stmt_list_tail_continue(stmts, ctx, ct_v)
        if need_ct:
            assert ct_v is not None
            core = [ILocalBlock(ct_v, core + _reset_lc_val(ct_v, ctx))]
        recompute = _reset_lc_val(lc, ctx) + _build_truth_incr_lc_br(cond, lc, ctx, br_v)
        body = core + recompute
    finally:
        ctx.loop_stack.pop()

    loop_instrs = _build_counter_loop_instrs(
        body, lc, lc, "==", "0", ctx, needs_entry_guard=False
    )
    if need_br:
        assert br_v is not None
        loop_instrs = [ILocalBlock(br_v, loop_instrs + _reset_lc_val(br_v, ctx))]
    return loop_instrs


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
    if isinstance(init, c.ExprList):
        # `for (i=0, j=10; ...; ...)`: ogni Assignment/FuncCall in sequenza.
        out: list[Instr] = []
        for e in init.exprs:
            if isinstance(e, (c.Assignment, c.FuncCall)):
                out.extend(_lower_stmt(e, ctx))
            else:
                out.extend(_lower_expr_as_stmt(e, ctx))
        return out
    raise MnemoCompileError(f"for-init non supportato: {type(init).__name__}")


def _lower_for(node: c.For, ctx: _Ctx) -> list[Instr]:
    # C99 `for (int i = …; …; …)`: `i` ha scope ristretto al for. Senza wrap
    # il declarator entra nel frame esterno e due `for(int i=…)` in sequenza
    # collidono in `_scope_declare`. Wrap solo se l'init dichiara un nome
    # nuovo (evita di disturbare scope outer per `for(;cond;next)`).
    needs_init_scope = isinstance(node.init, (c.Decl, c.DeclList))
    if needs_init_scope:
        _scope_enter(ctx)
    try:
        return _lower_for_body(node, ctx)
    finally:
        if needs_init_scope:
            _scope_exit(ctx)


def _lower_for_body(node: c.For, ctx: _Ctx) -> list[Instr]:
    pre = _lower_for_init(node.init, ctx)
    cond = node.cond if node.cond is not None else c.Constant("int", "1")
    noop_ct = _loop_body_continue_is_noop(node.stmt)
    if noop_ct:
        body_only: list[c.Node] = []
        body_scope_for = False
    elif isinstance(node.stmt, c.Compound):
        body_only = list(node.stmt.block_items or [])
        body_scope_for = True
    else:
        body_only = [node.stmt]
        body_scope_for = False

    lc = ctx.fresh_temp()
    need_br = _has_break_targeting_loop(node.stmt, False)
    need_ct = _has_continue_targeting_loop(node.stmt, False) and not noop_ct
    br_v = ctx.fresh_loop_ct() if need_br else None
    ct_v = ctx.fresh_loop_ct() if need_ct else None
    next_instrs = _lower_next_clause(node.next, ctx)
    next_part = _append_maybe_guarded_by_break(next_instrs, br_v)

    ctx.loop_stack.append(_LoopFrame(br_v, ct_v))
    try:
        if body_scope_for:
            _scope_enter(ctx)
            try:
                core = _lower_stmt_list_tail_continue(body_only, ctx, ct_v)
            finally:
                _scope_exit(ctx)
        else:
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
    loop_instrs = first_eval + _build_counter_loop_instrs(
        body, lc, lc, "==", "0", ctx, needs_entry_guard=True
    )
    if need_br:
        assert br_v is not None
        loop_instrs = [ILocalBlock(br_v, loop_instrs + _reset_lc_val(br_v, ctx))]
    return pre + loop_instrs


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
    return _lower_stmt(stmt, ctx)


def _lower_if(node: c.If, ctx: _Ctx) -> list[Instr]:
    then_instrs = _lower_substmt(node.iftrue, ctx)
    else_instrs: list[Instr] | None = (
        _lower_substmt(node.iffalse, ctx) if node.iffalse is not None else None
    )
    return _lower_if_from_expr(node.cond, then_instrs, else_instrs, ctx)


def _switch_case_label_str(it: c.Case, ctx: _Ctx) -> str:
    if isinstance(it.expr, c.Constant):
        return str(_const_int(it.expr))
    if isinstance(it.expr, c.ID) and it.expr.name in ctx.enum_constants:
        return str(ctx.enum_constants[it.expr.name])
    raise MnemoCompileError("switch: case richiede costante intera o enumeratore")


def _parse_switch_segments(
    items: list[c.Node], ctx: _Ctx
) -> list[_SwitchSeg]:
    """Raggruppa etichette consecutive e costruisce i segmenti (fall-through C)."""
    pending: list[str] = []
    segments: list[_SwitchSeg] = []
    for it in items:
        if isinstance(it, c.Case):
            pending.append(_switch_case_label_str(it, ctx))
            stmts = list(it.stmts or [])
            if stmts:
                segments.append(_SwitchSeg(list(pending), stmts))
                pending.clear()
        elif isinstance(it, c.Default):
            pending.append("default")
            stmts = list(it.stmts or [])
            if stmts:
                segments.append(_SwitchSeg(list(pending), stmts))
                pending.clear()
        else:
            raise MnemoCompileError(
                "nel corpo switch sono ammessi solo case e default"
            )
    if pending:
        raise MnemoCompileError(
            "switch: case/default con etichette ma senza istruzioni (usa `;` o un blocco)"
        )
    return segments


def _switch_flat_stmts_for_entry(
    segments: list[_SwitchSeg], start_i: int
) -> list[c.Node]:
    """
    Corpo C da eseguire entrando nel segmento `start_i`, con fall-through sui segmenti
    successivi fino a un `break` in coda a un segmento o alla fine dello switch.
    I `break` non vengono inclusi nell'output (solo terminano la catena).
    """
    acc: list[c.Node] = []
    j = start_i
    while j < len(segments):
        ss = segments[j].stmts
        for k, st in enumerate(ss):
            if isinstance(st, c.Break):
                if k != len(ss) - 1:
                    raise MnemoCompileError(
                        "switch: `break` deve essere l'ultima istruzione del case"
                    )
                return acc
            acc.append(st)
        j += 1
    return acc


def _reject_switch_flat_unstructured_break(flat: list[c.Node]) -> None:
    """
    `break` annidato (es. dentro `if`) richiederebbe gating per istruzione annidato in
    `if (disc==v)` e rompe la reversibilità IF/FI della VM. Solo corpi «piatti».
    """
    if not flat:
        return
    coord = flat[0].coord
    wrapped = c.Compound(block_items=list(flat), coord=coord)
    if _has_break_targeting_loop(wrapped, False):
        raise MnemoCompileError(
            "switch: `break` solo in fondo al case (non dentro if/altri costrutti)"
        )


def _lower_switch_flat_body(segments: list[_SwitchSeg], start_i: int, ctx: _Ctx) -> list[Instr]:
    flat = _switch_flat_stmts_for_entry(segments, start_i)
    _reject_switch_flat_unstructured_break(flat)
    out: list[Instr] = []
    for s in flat:
        out.extend(_lower_stmt(s, ctx))
    return out


def _switch_value_to_segment(
    segments: list[_SwitchSeg],
) -> dict[str, int]:
    m: dict[str, int] = {}
    for i, seg in enumerate(segments):
        for v in seg.values:
            if v == "default":
                continue
            if v in m:
                raise MnemoCompileError(f"switch: etichetta case duplicata ({v})")
            m[v] = i
    return m


def _emit_switch_if_chain(
    disc: str,
    sorted_vals: list[str],
    val_to_seg: dict[str, int],
    segments: list[_SwitchSeg],
    default_i: int | None,
    ctx: _Ctx,
) -> list[Instr]:
    if default_i is not None:
        rest: list[Instr] = _lower_switch_flat_body(segments, default_i, ctx)
    else:
        rest = []
    for v in reversed(sorted_vals):
        si = val_to_seg[v]
        body = _lower_switch_flat_body(segments, si, ctx)
        rest = [IIfKairos(disc, "==", v, body, rest if rest else None)]
    return rest


def _lower_switch(node: c.Switch, ctx: _Ctx) -> list[Instr]:
    if not isinstance(node.stmt, c.Compound):
        raise MnemoCompileError("switch: il corpo deve essere { ... }")
    pre_d, disc_var, tm_d = _kairos_atom(node.cond, ctx)
    segments = _parse_switch_segments(node.stmt.block_items or [], ctx)
    if not segments:
        out = list(pre_d)
        _append_cond_cleanup(out, ctx, tm_d)
        return out

    default_slots = [i for i, s in enumerate(segments) if "default" in s.values]
    if len(default_slots) > 1:
        raise MnemoCompileError("switch: più di un `default`")
    default_i = default_slots[0] if default_slots else None

    val_to_seg = _switch_value_to_segment(segments)
    if not val_to_seg and default_i is None:
        raise MnemoCompileError("switch: nessun `case` né `default`")

    sorted_vals = sorted(val_to_seg.keys(), key=lambda k: int(k, 0))
    chain = _emit_switch_if_chain(
        disc_var,
        sorted_vals,
        val_to_seg,
        segments,
        default_i,
        ctx,
    )
    out = list(pre_d) + chain
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
                    ctx.struct_specs[st.name] = _flatten_struct_fields(
                        st,
                        struct_specs=ctx.struct_specs,
                        typedef_map=ctx.typedef_map,
                    )
                return []
            return []

        ut = _union_tag_for_decl_type(node.type, ctx)
        if ut is not None:
            if not isinstance(node.type, c.TypeDecl) or node.type.declname is None:
                raise MnemoCompileError("union: nome variabile mancante")
            varname = str(node.type.declname)
            logical = _scope_declare(ctx, varname)
            if ut not in ctx.union_specs:
                raise MnemoCompileError(f"union {ut}: definizione mancante")
            ctx.union_tag_of_var[logical] = ut
            ctx.int_locals.add(logical)
            if ctx.mem_layout is None:
                ctx.decl_order.append(logical)
            ctx.var_types[logical] = node.type
            if node.init is not None:
                ini_u = node.init
                if isinstance(ini_u, c.InitList):
                    flat_u = _flatten_init_list(ini_u)
                    if len(flat_u) != 1:
                        raise MnemoCompileError("init union: un solo valore in `{ ... }`")
                    return _lower_assign(_phys(ctx, logical), flat_u[0], ctx)
                if isinstance(ini_u, c.ExprList):
                    ini_u = _fold_exprlist_as_comma_chain(ini_u)
                return _lower_assign(_phys(ctx, logical), ini_u, ctx)
            return []

        st_tag = _struct_tag_for_decl_type(node.type, ctx)
        if st_tag is not None:
            if not isinstance(node.type, c.TypeDecl) or node.type.declname is None:
                raise MnemoCompileError("struct: nome variabile mancante")
            varname = str(node.type.declname)
            logical = _scope_declare(ctx, varname)
            fields = ctx.struct_specs.get(st_tag)
            if not fields:
                raise MnemoCompileError(f"struct {st_tag}: definizione mancante")
            ctx.struct_tag_of_var[logical] = st_tag
            for fn, fty in fields:
                if _type_node_is_pthread_mutex(fty, ctx.typedef_map):
                    continue
                loc = _struct_field_local(logical, fn)
                ctx.int_locals.add(loc)
                if ctx.mem_layout is None:
                    ctx.decl_order.append(loc)
                ctx.var_types[loc] = fty
            if node.init is not None:
                # `struct V v = f(...);` — init da FuncCall che ritorna struct
                # con stessa firma. Multi-word return su tutte le celle dei campi.
                if isinstance(node.init, c.FuncCall):
                    if ctx.mem_layout is None or ctx.file_ast is None:
                        raise MnemoCompileError(
                            "init struct da call: layout/AST mancante"
                        )
                    norm_sc, callee = _resolve_indirect_callee(node.init, ctx)
                    fd_u = _get_funcdef(ctx.file_ast, callee)
                    if fd_u is None or not isinstance(fd_u.decl.type, c.FuncDecl):
                        raise MnemoCompileError(
                            f"init struct da `{callee}()`: funzione non trovata"
                        )
                    callee_fd = fd_u.decl.type
                    sz_lhs = _sizeof_struct_tag(st_tag, ctx)
                    rw_lhs = _return_words_from_bytes(sz_lhs)
                    sz_ret = _sizeof_return_bytes(callee_fd, ctx)
                    rw_c = ctx.mem_layout.ret_words.get(callee, 0)
                    if (
                        sz_ret != sz_lhs
                        or rw_c != rw_lhs
                        or rw_c != len(fields)
                    ):
                        raise MnemoCompileError(
                            f"init struct da `{callee}()`: tipo di ritorno incompatibile"
                        )
                    sinks = [
                        _phys(ctx, _struct_field_local(logical, fn))
                        for fn, _ in fields
                    ]
                    return _lower_funccall_with_ret(norm_sc, ctx, sinks)
                if not isinstance(node.init, c.InitList):
                    raise MnemoCompileError("init struct: serve `{ ... }`")
                has_named_s = any(
                    isinstance(e, c.NamedInitializer) for e in node.init.exprs
                )
                out_s: list[Instr] = []
                if has_named_s:
                    field_order = [
                        fn for fn, fty in fields
                        if not _type_node_is_pthread_mutex(fty, ctx.typedef_map)
                    ]
                    pos = 0
                    for e in node.init.exprs:
                        if isinstance(e, c.NamedInitializer):
                            if len(e.name) != 1 or not isinstance(e.name[0], c.ID):
                                raise MnemoCompileError(
                                    "designated init struct: solo `.field = expr`"
                                )
                            fname = e.name[0].name
                            if fname not in field_order:
                                raise MnemoCompileError(
                                    f"designated init struct: campo `.{fname}` non in struct"
                                )
                            loc = _struct_field_local(logical, fname)
                            out_s.extend(_lower_assign(_phys(ctx, loc), e.expr, ctx))
                            pos = field_order.index(fname) + 1
                        else:
                            if pos >= len(field_order):
                                raise MnemoCompileError(
                                    "init struct: troppi elementi posizionali"
                                )
                            loc = _struct_field_local(logical, field_order[pos])
                            out_s.extend(_lower_assign(_phys(ctx, loc), e, ctx))
                            pos += 1
                    return out_s
                flat_s = _flatten_init_list(node.init)
                ix = 0
                for fn, fty in fields:
                    if _type_node_is_pthread_mutex(fty, ctx.typedef_map):
                        continue
                    if ix >= len(flat_s):
                        break
                    loc = _struct_field_local(logical, fn)
                    out_s.extend(_lower_assign(_phys(ctx, loc), flat_s[ix], ctx))
                    ix += 1
                if ix < len(flat_s):
                    raise MnemoCompileError("init struct: troppi elementi in `{ ... }`")
                return out_s
            return []

        ap = _try_parse_array_decl(node, ctx)
        if ap is not None:
            name, dims, esz = ap
            tot = int(math.prod(dims))
            logical = _scope_declare(ctx, name)
            ctx.array_info[logical] = _ArrayInfo(dims=dims, total=tot, elem_size=esz)
            ctx.var_types[logical] = node.type
            for i in range(tot):
                cell = _array_elem_local(logical, i)
                ctx.int_locals.add(cell)
                if ctx.mem_layout is None:
                    ctx.decl_order.append(cell)
            if node.init is None:
                return []
            if isinstance(node.init, c.InitList):
                has_named = any(isinstance(e, c.NamedInitializer) for e in node.init.exprs)
                out: list[Instr] = []
                if has_named:
                    if len(dims) == 1:
                        dense = _array_init_dense_1d(node.init, tot)
                    else:
                        dense = _array_init_dense_nd(node.init, list(dims))
                    for j, el in enumerate(dense):
                        if el is None:
                            continue
                        out.extend(
                            _lower_assign(
                                _phys(ctx, _array_elem_local(logical, j)), el, ctx
                            )
                        )
                    return out
                flat = _flatten_init_list(node.init)
                for j, el in enumerate(flat):
                    if j >= tot:
                        break
                    out.extend(
                        _lower_assign(
                            _phys(ctx, _array_elem_local(logical, j)), el, ctx
                        )
                    )
                return out
            # `char s[] = "literal";` o `char s[N] = "lit";`: scrive byte-per-byte
            # con NUL implicito, allineato col layout già allocato.
            if (
                isinstance(node.init, c.Constant)
                and node.init.type == "string"
                and len(dims) == 1
            ):
                s = _literal_c_string(node.init)
                b = s.encode("utf-8")
                out2: list[Instr] = []
                # Mnemo non scrive il NUL trailing perché celle inizializzano a 0.
                for j, byte in enumerate(b):
                    if j >= tot:
                        break
                    if byte == 0:
                        continue
                    out2.extend(
                        _lower_assign(
                            _phys(ctx, _array_elem_local(logical, j)),
                            c.Constant("int", str(int(byte))),
                            ctx,
                        )
                    )
                return out2
            raise MnemoCompileError(
                "array: inizializzatore `{ … }` oppure nessuno (non un singolo valore)"
            )

        imm = _immediate_named_scalar_typedef(node)
        if imm == "pthread_mutex_t":
            if not isinstance(node.type, c.TypeDecl) or node.type.declname is None:
                raise MnemoCompileError("pthread_mutex_t: nome variabile mancante")
            name = str(node.type.declname)
            logical = _scope_declare(ctx, name)
            kai = f"__mn_mtx_{logical}"
            ctx.channel_kairos[logical] = kai
            ctx.channel_decl_order.append(logical)
            ctx.var_types[logical] = node.type
            if node.init is not None:
                raise MnemoCompileError("pthread_mutex_t: niente inizializzatore")
            return []

        imm_pi = _immediate_named_scalar_typedef(node)
        if imm_pi == "mnemo_kairos_channel_t":
            if not isinstance(node.type, c.TypeDecl) or node.type.declname is None:
                raise MnemoCompileError("mnemo_kairos_channel_t: nome variabile mancante")
            name = str(node.type.declname)
            logical = _scope_declare(ctx, name)
            kai = f"__mn_kch_{logical}"
            ctx.channel_kairos[logical] = kai
            ctx.channel_decl_order.append(logical)
            ctx.var_types[logical] = node.type
            if node.init is not None:
                raise MnemoCompileError("mnemo_kairos_channel_t: niente inizializzatore")
            return []

        td = ctx.typedef_map
        name = _scalar_decl_name(node, td)
        if name is None:
            name = _enum_scalar_decl_name(node)
        if name is None:
            fp_meta = _func_ptr_decl_meta(node, td)
            if fp_meta is not None:
                fp_name, _cfd = fp_meta
                logical_fp = _scope_declare(ctx, fp_name)
                ctx.int_locals.add(logical_fp)
                if ctx.mem_layout is None:
                    ctx.decl_order.append(logical_fp)
                ctx.var_types[logical_fp] = node.type
                ctx.func_ptr_vars.add(logical_fp)
                ctx.use_hist = True
                phy_fp = _phys(ctx, logical_fp)
                out_fp: list[Instr] = [
                    IHistPush(ctx.hist, phy_fp),
                    IAddEq(phy_fp, Imm(0)),
                ]
                if node.init is not None:
                    ini = node.init
                    if isinstance(ini, c.ExprList):
                        ini = _fold_exprlist_as_comma_chain(ini)
                    tgt_fp = _parse_function_designator(ini, ctx)
                    if tgt_fp is None:
                        raise MnemoCompileError(
                            "puntatore a funzione: inizializzatore deve essere "
                            "`nome_funzione` o `&nome_funzione`"
                        )
                    ctx.func_ptr_alias[logical_fp] = tgt_fp
                return out_fp
            pn = _int_ptr_var_decl_name(node, td)
            if pn is None:
                pn = _struct_pointer_param_name(node, ctx)
            if pn is None:
                raise MnemoCompileError(
                    f"dichiarazione non supportata: {type(node.type).__name__}"
                )
            name = pn
            ptr_lit = _char_ptr_string_literal_meta(node, td, ctx.fn_name)
            if ptr_lit is not None:
                _ros_meta_base, tot, b = ptr_lit
                logical = _scope_declare(ctx, name)
                sbase = f"__mn_ros_{ctx.fn_name}_{logical}"
                if sbase in ctx.array_info:
                    raise MnemoCompileError(f"ridichiarazione: {sbase}")
                ctx.array_info[sbase] = _ArrayInfo(
                    dims=(tot,), total=tot, elem_size=1
                )
                for i in range(tot):
                    cell = _array_elem_local(sbase, i)
                    if cell in ctx.int_locals:
                        raise MnemoCompileError(f"ridichiarazione: {cell}")
                    ctx.int_locals.add(cell)
                    if ctx.mem_layout is None:
                        ctx.decl_order.append(cell)
                ctx.int_locals.add(logical)
                if ctx.mem_layout is None:
                    ctx.decl_order.append(logical)
                ctx.var_types[logical] = node.type
                ctx.char_ptr_string_base[logical] = sbase
                try:
                    ctx.char_ptr_string_value[logical] = b.decode("utf-8")
                except UnicodeDecodeError:
                    ctx.char_ptr_string_value[logical] = b.decode(
                        "utf-8", errors="replace"
                    )
                out: list[Instr] = []
                for i, byte in enumerate(b):
                    out.extend(
                        _lower_assign(
                            _phys(ctx, _array_elem_local(sbase, i)),
                            c.Constant("int", str(byte)),
                            ctx,
                        )
                    )
                out.extend(
                    _lower_assign(
                        _phys(ctx, _array_elem_local(sbase, tot - 1)),
                        c.Constant("int", "0"),
                        ctx,
                    )
                )
                first = _array_elem_local(sbase, 0)
                k = ctx.slot_index.get(first)
                if k is None:
                    raise MnemoCompileError(
                        "layout: indirizzo base stringa letterale mancante"
                    )
                ctx.use_hist = True
                phy = _phys(ctx, logical)
                out.extend([IHistPush(ctx.hist, phy), IAddEq(phy, Imm(k))])
                return out
        logical = _scope_declare(ctx, name)
        ctx.int_locals.add(logical)
        if ctx.mem_layout is None:
            ctx.decl_order.append(logical)
        ctx.var_types[logical] = node.type
        if node.init is None:
            return []
        if isinstance(node.init, c.InitList):
            raise MnemoCompileError("init struct/array non supportato")
        rhs_init = node.init
        if isinstance(rhs_init, c.ExprList):
            rhs_init = _fold_exprlist_as_comma_chain(rhs_init)
        return _lower_assign(_phys(ctx, logical), rhs_init, ctx)

    if isinstance(node, c.Assignment):
        if (
            isinstance(node.lvalue, c.ID)
            and node.op == "="
            and _scope_resolve(ctx, node.lvalue.name) in ctx.func_ptr_vars
        ):
            lhs_fp = _scope_resolve(ctx, node.lvalue.name)
            rhs_fp = node.rvalue
            if isinstance(rhs_fp, c.ExprList):
                rhs_fp = _fold_exprlist_as_comma_chain(rhs_fp)
            if isinstance(rhs_fp, c.ID):
                rlog = _scope_resolve(ctx, rhs_fp.name)
                if rlog in ctx.func_ptr_alias:
                    ctx.func_ptr_alias[lhs_fp] = ctx.func_ptr_alias[rlog]
                    return []
            tgt_as = _parse_function_designator(rhs_fp, ctx)
            if tgt_as is None:
                raise MnemoCompileError(
                    "assegnamento a puntatore a funzione: usa `g`, `&g`, o copia da "
                    "un altro puntatore già inizializzato"
                )
            ctx.func_ptr_alias[lhs_fp] = tgt_as
            return []
        if (
            node.op == "="
            and isinstance(node.lvalue, c.ID)
            and isinstance(node.rvalue, c.FuncCall)
        ):
            lhs = _scope_resolve(ctx, node.lvalue.name)
            if (
                lhs in ctx.struct_tag_of_var
                and ctx.mem_layout is not None
                and ctx.file_ast is not None
            ):
                norm_sc, callee = _resolve_indirect_callee(node.rvalue, ctx)
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
                        return _lower_funccall_with_ret(norm_sc, ctx, sinks)
        if isinstance(node.lvalue, c.StructRef):
            if node.lvalue.type == "->":
                if node.op == "=":
                    return _lower_struct_arrow_assign(node.lvalue, node.rvalue, ctx)
                if node.op in _COMPOUND_ASSIGN_OPS:
                    coord = node.coord
                    rhs = c.BinaryOp(
                        _COMPOUND_ASSIGN_OPS[node.op],
                        node.lvalue,
                        node.rvalue,
                        coord,
                    )
                    return _lower_struct_arrow_assign(node.lvalue, rhs, ctx)
                raise MnemoCompileError(
                    f"ptr->campo: assegnamento con {node.op!r} non supportato"
                )
            base, path = _structref_base_and_path(node.lvalue)
            base_log = _scope_resolve(ctx, base)
            mangled = "__".join(path)
            if base_log in ctx.union_tag_of_var:
                if len(path) != 1:
                    raise MnemoCompileError("union: un solo livello di campo")
                field = path[0]
                tag = ctx.union_tag_of_var[base_log]
                spec = ctx.union_specs.get(tag)
                if not spec or field not in [fn for fn, _ in spec]:
                    raise MnemoCompileError(f"union {tag}: membro {field!r} assente")
                if node.op == "=":
                    return _lower_assign(_phys(ctx, base_log), node.rvalue, ctx)
                if node.op in _COMPOUND_ASSIGN_OPS:
                    rhs = c.BinaryOp(
                        _COMPOUND_ASSIGN_OPS[node.op],
                        node.lvalue,
                        node.rvalue,
                        node.coord,
                    )
                    return _lower_assign(_phys(ctx, base_log), rhs, ctx)
                raise MnemoCompileError(f"assegnamento union con {node.op!r} non supportato")
            if base_log not in ctx.struct_tag_of_var:
                raise MnemoCompileError(f"{base!r} non è una variabile struct")
            tag = ctx.struct_tag_of_var[base_log]
            spec = ctx.struct_specs.get(tag)
            if not spec or mangled not in [fn for fn, _ in spec]:
                raise MnemoCompileError(f"struct {tag}: campo {mangled!r} assente")
            cell = _struct_field_local(base_log, mangled)
            if node.op == "=":
                return _lower_assign(_phys(ctx, cell), node.rvalue, ctx)
            if node.op in _COMPOUND_ASSIGN_OPS:
                coord = node.coord
                rhs = c.BinaryOp(
                    _COMPOUND_ASSIGN_OPS[node.op],
                    node.lvalue,
                    node.rvalue,
                    coord,
                )
                return _lower_assign(_phys(ctx, cell), rhs, ctx)
            raise MnemoCompileError(
                f"struct: assegnamento con {node.op!r} non supportato"
            )
        if isinstance(node.lvalue, c.ArrayRef):
            lv = node.lvalue
            # `(*p)[i] = X` → `*(p + i) = X`
            if (
                isinstance(lv.name, c.UnaryOp) and lv.name.op == "*"
                and isinstance(lv.name.expr, c.ID)
            ):
                pid = lv.name.expr
                new_lv = c.UnaryOp(
                    "*",
                    c.BinaryOp("+", pid, lv.subscript, lv.coord),
                    lv.coord,
                )
                new_assign = c.Assignment(node.op, new_lv, node.rvalue, node.coord)
                return _lower_stmt(new_assign, ctx)
            # `p[i] = X` su puntatore (non array): rewrite a `*(p + i) = X`.
            if isinstance(lv.name, c.ID):
                base_log = _scope_resolve(ctx, lv.name.name)
                if (
                    base_log not in ctx.array_info
                    and base_log in ctx.int_locals
                ):
                    new_lv = c.UnaryOp(
                        "*",
                        c.BinaryOp("+", lv.name, lv.subscript, lv.coord),
                        lv.coord,
                    )
                    new_assign = c.Assignment(node.op, new_lv, node.rvalue, node.coord)
                    return _lower_stmt(new_assign, ctx)
            base, subs = _flatten_array_ref_chain(node.lvalue)
            if node.op == "=":
                return _lower_array_subscript_assign(base, subs, node.rvalue, ctx)
            if node.op in _COMPOUND_ASSIGN_OPS:
                coord = node.coord
                rhs = c.BinaryOp(
                    _COMPOUND_ASSIGN_OPS[node.op],
                    node.lvalue,
                    node.rvalue,
                    coord,
                )
                return _lower_array_subscript_assign(base, subs, rhs, ctx)
            raise MnemoCompileError(
                f"array[…]: assegnamento con {node.op!r} non supportato"
            )
        if isinstance(node.lvalue, c.UnaryOp) and node.lvalue.op == "*":
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
            if node.op == "=":
                rhs = node.rvalue
            elif node.op in _COMPOUND_ASSIGN_OPS:
                rhs = c.BinaryOp(
                    _COMPOUND_ASSIGN_OPS[node.op],
                    node.lvalue,
                    node.rvalue,
                    node.coord,
                )
            else:
                raise MnemoCompileError(
                    f"assegnamento a *p con {node.op!r} non supportato"
                )
            rest = _lower_deref_assign_phys(ptrn, rhs, ctx)
            post = [IHistPush(ctx.scratch, x) for x in reversed(tm_p)]
            if tm_p:
                ctx.use_scratch = True
            return ei_p + rest + post
        if not isinstance(node.lvalue, c.ID):
            raise MnemoCompileError("lvalue non-ID non supportato")
        lhs = _scope_resolve(ctx, node.lvalue.name)
        if lhs not in ctx.int_locals:
            raise MnemoCompileError(
                f"assegnamento a variabile non dichiarata: {node.lvalue.name}"
            )
        if node.op == "=":
            return _lower_assign(_phys(ctx, lhs), node.rvalue, ctx)
        if node.op in _COMPOUND_ASSIGN_OPS:
            coord = node.coord
            # Nota Janus: `_lower_assign` fa eval(rhs) *prima* di push(lhs) che azzera lhs.
            # Per `sum += i` serve rhs = sum+i così il totale è calcolato prima del push.
            rhs = c.BinaryOp(
                _COMPOUND_ASSIGN_OPS[node.op],
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
        node, nm = _resolve_indirect_callee(node, ctx)
        pthread_ins = _lower_pthread_mnemo_call(node, ctx)
        if pthread_ins is not None:
            if nm == "mnemo_pthread_parallel2" and any(
                isinstance(ins, IPar) for ins in pthread_ins
            ):
                ctx.after_par_join = True
            return pthread_ins
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
        _scope_enter(ctx)
        out = _lower_compound_block_items(list(node.block_items or []), ctx)
        _scope_exit(ctx)
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
        if isinstance(node, c.FuncCall) and isinstance(node.name, c.ID):
            if node.name.name == "printf":
                needed.update(
                    {
                        "helpers.kairos",
                        "mul.kairos",
                        "divmod.kairos",
                        "putd.kairos",
                        "putx.kairos",
                    }
                )
        if isinstance(node, c.Assignment):
            if node.op in ("<<=", ">>=", "&=", "|="):
                needed.update(
                    {
                        "helpers.kairos",
                        "mul.kairos",
                        "divmod.kairos",
                        "bits.kairos",
                    }
                )
        if isinstance(node, c.BinaryOp):
            if node.op == "*":
                needed.add("mul.kairos")
            elif node.op == "/":
                needed.add("helpers.kairos")
                needed.add("divmod.kairos")
            elif node.op == "%":
                needed.add("helpers.kairos")
                needed.add("mod.kairos")
            elif node.op in ("&", "|", "<<", ">>"):
                needed.add("helpers.kairos")
                needed.add("mul.kairos")
                needed.add("divmod.kairos")
                needed.add("bits.kairos")
        if isinstance(node, c.ArrayRef):
            # Multi-D ArrayRef (es. m[i][j]): lowering genera implicitamente
            # __mn_mul_into per il calcolo dell'indice riga-maggiore i*COLS+j.
            # Senza `*` esplicito nel C source, mul.kairos non sarebbe incluso.
            if isinstance(node.name, c.ArrayRef):
                needed.add("mul.kairos")
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
        "bits.kairos",
        "putd.kairos",
        "putx.kairos",
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
        "bits.kairos",
        "putd.kairos",
        "putx.kairos",
        "ptr_pool.kairos",
    ]
    head = [n for n in order if n in needed]
    tail = sorted(needed.difference(head))
    return head + tail


def _register_file_scope_struct_union_tags(
    ctx: _Ctx, file_ast: c.FileAST
) -> None:
    """
    In main le dichiarazioni file-scope popolano struct_tag_of_var / union_tag_of_var
    e array_info (per array a file-scope); nelle procedure utente va ripetuto,
    altrimenti `mps.client_done` non risolve `mps`.
    """
    for ext in file_ast.ext:
        if not isinstance(ext, c.Decl):
            continue
        if isinstance(ext.type, c.FuncDecl):
            continue
        if isinstance(ext.type, c.ArrayDecl):
            ap = _try_parse_array_decl(ext, ctx)
            if ap is not None:
                name, dims, esz = ap
                tot = int(math.prod(dims))
                ctx.array_info[name] = _ArrayInfo(
                    dims=dims, total=tot, elem_size=esz
                )
                ctx.var_types[name] = ext.type
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


def _locals_list(ctx: _Ctx, *, for_main: bool = True) -> list[tuple[str, str]]:
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
    for pn in ctx.par_branch_stack_names:
        locals_list.append(("stack", pn))
    if for_main:
        # Ogni `ICall` a procedure user/lib passa `_kairos_stack_actuals` (hist + scratch):
        # `main` deve dichiararli sempre, anche se `use_scratch` non è mai stato impostato
        # (la VM segnala `__mn_scratch` non def se solo la procedura callee usa scratch).
        locals_list.append(("stack", ctx.hist))
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
    file_scope_channel_order: tuple[str, ...] = (),
    file_scope_channel_kairos: dict[str, str] | None = None,
    opt_uncall_user_calls: bool = False,
    uncall_excluded_via_vm_targets: frozenset[str] = frozenset(),
    channel_using_targets: frozenset[str] = frozenset(),
    par2_workers: frozenset[str] = frozenset(),
    callee_mem_touches: dict[str, frozenset[int]] | None = None,
) -> Function:
    name = fdef.decl.name
    fd = fdef.decl.type
    if not isinstance(fd, c.FuncDecl):
        raise MnemoCompileError("definizione funzione malformata")
    if _func_decl_has_variadic(fd):
        raise MnemoCompileError(
            f"{name}: definizioni con argomenti variadici (`...`) non supportate"
        )
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
        opt_uncall_user_calls=opt_uncall_user_calls,
        uncall_excluded_via_vm_targets=uncall_excluded_via_vm_targets,
        channel_using_targets=channel_using_targets,
        par2_workers=par2_workers,
        callee_mem_touches=callee_mem_touches or {},
    )
    _bind_ctx_layout(ctx, layout, name)
    ctx.file_scope_channel_order = file_scope_channel_order
    if file_scope_channel_kairos:
        ctx.channel_kairos.update(file_scope_channel_kairos)
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
    _ct_self = (callee_mem_touches or {}).get(name)
    if _ct_self is None:
        param_order = [f"__mn_mem{i}" for i in range(layout.total_cells)]
    else:
        param_order = [f"__mn_mem{i}" for i in sorted(_ct_self)]

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
            ap = _try_parse_array_decl(p, ctx)
            if ap is not None:
                aname, dims, esz = ap
                tot = int(math.prod(dims))
                ctx.array_info[aname] = _ArrayInfo(
                    dims=dims,
                    total=tot,
                    elem_size=esz,
                    array_decay_pointer=True,
                )
            else:
                # `int *a` come parametro: treat as decay-array di size ARR_MAX
                # backed da pool slot. Permette `a[i]` lowerato via pool_load.
                pname = _int_ptr_var_decl_name(p, file_td)
                if pname is not None and pname not in ctx.array_info:
                    ctx.array_info[pname] = _ArrayInfo(
                        dims=[ARR_MAX],
                        total=ARR_MAX,
                        elem_size=4,
                        array_decay_pointer=True,
                    )
    for p in fd.args.params if fd.args else []:
        if isinstance(p, c.Decl):
            st_tag = _struct_tag_for_decl_type(p.type, ctx)
            if st_tag is not None and isinstance(p.type, c.TypeDecl):
                dn = p.type.declname
                if dn is not None:
                    ctx.struct_tag_of_var[str(dn)] = st_tag

    ctx.param_storage_order = tuple(_func_param_storage_names(fd, file_td, pm))

    _register_param_var_types(ctx, fd)
    _scope_init_params(ctx, ctx.param_storage_order)

    ch_pi_formals: list[tuple[str, str]] = []
    for p in fd.args.params if fd.args else []:
        if isinstance(p, c.Decl):
            if _immediate_named_scalar_typedef(p) == "mnemo_kairos_channel_t":
                if not isinstance(p.type, c.TypeDecl) or p.type.declname is None:
                    continue
                pname = str(p.type.declname)
                if pname in ctx.channel_kairos:
                    raise MnemoCompileError(
                        f"`{name}`: parametro canale π `{pname}`: nome già usato "
                        "(file-scope o altro parametro canale)"
                    )
                kai = f"__mn_kch_{pname}"
                ctx.channel_kairos[pname] = kai
                ch_pi_formals.append(("channel", kai))

    instrs = _lower_compound_block_items(list(body.block_items or []), ctx)

    ch_formals = [
        ("channel", ctx.channel_kairos[m]) for m in ctx.file_scope_channel_order
    ]
    stack_formals: list[tuple[str, str]] = [
        ("stack", ctx.hist),
        ("stack", ctx.scratch),
    ]
    return Function(
        name=name,
        params=[("int", p) for p in param_order]
        + ch_pi_formals
        + ch_formals
        + stack_formals,
        locals=_locals_list(ctx, for_main=False),
        blocks=[Block("entry", [IComment(f"funzione C {name}")] + instrs)],
    )


def _rename_decl_type(type_node: c.Node, new_name: str) -> c.Node:
    """Clona shallow `type_node` (ArrayDecl/PtrDecl/TypeDecl) sostituendo il declname
    interno (TypeDecl.declname) con `new_name`. Usato per hoist di CompoundLiteral:
    Typename ha declname=None, ma il Decl sintetico richiede il nome reale.
    """
    if isinstance(type_node, c.TypeDecl):
        return c.TypeDecl(
            declname=new_name,
            quals=list(type_node.quals or []),
            align=type_node.align,
            type=type_node.type,
            coord=type_node.coord,
        )
    if isinstance(type_node, c.ArrayDecl):
        return c.ArrayDecl(
            type=_rename_decl_type(type_node.type, new_name),
            dim=type_node.dim,
            dim_quals=list(type_node.dim_quals or []),
            coord=type_node.coord,
        )
    if isinstance(type_node, c.PtrDecl):
        return c.PtrDecl(
            quals=list(type_node.quals or []),
            type=_rename_decl_type(type_node.type, new_name),
            coord=type_node.coord,
        )
    return type_node


def _hoist_compound_literals(funcdef: c.FuncDef) -> list[c.Decl]:
    """Hoist `(T[]){...}` / `(struct T){...}` compound literals nel body della funzione
    come Decl sintetici. Sostituisce ogni `CompoundLiteral` con `ID(name)`. Restituisce
    la lista dei Decl da prependere al body.

    Mnemo non supporta CompoundLiteral come espressione perché la sua memoria è
    pre-allocata da `layout_collect.py` per ogni decl statico; hoisting trasforma
    il pattern in una sequenza Decl(hidden) + ID-ref, riusando le pipeline esistenti.
    """
    new_decls: list[c.Decl] = []
    counter = [0]

    def make_decl(cl: c.CompoundLiteral) -> c.Decl:
        name = f"__mn_cl{counter[0]}"
        counter[0] += 1
        type_node = cl.type.type
        # `int[]` (no dim): inferisci dim da InitList length
        if isinstance(type_node, c.ArrayDecl) and type_node.dim is None and isinstance(cl.init, c.InitList):
            n = len(cl.init.exprs or [])
            type_node = c.ArrayDecl(
                type=type_node.type,
                dim=c.Constant("int", str(n), cl.coord),
                dim_quals=list(type_node.dim_quals or []),
                coord=type_node.coord,
            )
        decl_type = _rename_decl_type(type_node, name)
        return c.Decl(
            name=name,
            quals=[],
            align=[],
            storage=[],
            funcspec=[],
            type=decl_type,
            init=cl.init,
            bitsize=None,
            coord=cl.coord,
        )

    def visit(node: c.Node | None) -> None:
        if node is None:
            return
        # Walk children: pycparser slots include sub-Node attrs.
        for attr in getattr(node, "__slots__", ()):
            if attr in ("coord", "__weakref__"):
                continue
            val = getattr(node, attr, None)
            if isinstance(val, c.CompoundLiteral):
                d = make_decl(val)
                # Ricorri SUL contenuto della CompoundLiteral prima di hoist
                # (es. nested CL — improbabile ma safe).
                visit(val.init)
                new_decls.append(d)
                setattr(node, attr, c.ID(d.name, val.coord))
            elif isinstance(val, list):
                for i, item in enumerate(val):
                    if isinstance(item, c.CompoundLiteral):
                        d = make_decl(item)
                        visit(item.init)
                        new_decls.append(d)
                        val[i] = c.ID(d.name, item.coord)
                    elif hasattr(item, "__slots__"):
                        visit(item)
            elif hasattr(val, "__slots__"):
                visit(val)

    visit(funcdef.body)
    return new_decls


def _scalar_int_decl_name_for_init(decl: c.Decl, file_td: dict[str, c.Node]) -> str | None:
    """Se `decl` è un Decl scalare `int`/typedef-of-int/enum (no struct/union/array/ptr),
    ritorna il nome del declarator; altrimenti None. Usato per inferire i Decl
    file-scope che supportano init Constant."""
    if decl.init is None or decl.name is None:
        return None
    t = decl.type
    if not isinstance(t, c.TypeDecl):
        return None
    inner = t.type
    if isinstance(inner, c.IdentifierType):
        names = inner.names
        if _is_scalar_type_names(names, file_td):
            return decl.name
    if isinstance(inner, c.Enum):
        return decl.name
    return None


def _int_constant_value(node: c.Node) -> int | None:
    """Valuta letteralmente `node` come int. None se non è Constant int/char/bool
    o UnaryOp `-` su Constant. Conservativo — non valuta espressioni complesse."""
    if isinstance(node, c.Constant):
        try:
            if node.type == "char":
                v = node.value.strip("'")
                if len(v) == 1:
                    return ord(v)
                if v.startswith("\\"):
                    esc = {"n": 10, "t": 9, "r": 13, "0": 0, "\\": 92, "'": 39}
                    return esc.get(v[1])
                return None
            return int(node.value, 0)
        except (ValueError, AttributeError):
            return None
    if isinstance(node, c.UnaryOp) and node.op in ("-", "+"):
        inner = _int_constant_value(node.expr)
        if inner is None:
            return None
        return -inner if node.op == "-" else inner
    return None


def _convert_kr_to_ansi(ast: c.FileAST) -> None:
    """K&R function defs (`int foo(a, b) int a; int b; { … }`) → ANSI.
    Per ogni FuncDef con `param_decls` non vuoto, sostituisce gli `c.ID`
    in `decl.type.args.params` con i `c.Decl` di matching name dal
    `param_decls`, poi azzera `param_decls`.
    """
    for ext in ast.ext:
        if not isinstance(ext, c.FuncDef):
            continue
        if not getattr(ext, "param_decls", None):
            continue
        param_decls = ext.param_decls
        fd = ext.decl.type
        if not isinstance(fd, c.FuncDecl) or fd.args is None:
            continue
        by_name: dict[str, c.Decl] = {
            d.name: d for d in param_decls if isinstance(d, c.Decl) and d.name
        }
        new_params: list[c.Node] = []
        for p in fd.args.params:
            if isinstance(p, c.ID) and p.name in by_name:
                new_params.append(by_name[p.name])
            else:
                new_params.append(p)
        fd.args.params = new_params
        ext.param_decls = None


def _name_anonymous_structs_unions(ast: c.FileAST) -> None:
    """Assegna nomi sintetici a `struct {...}` / `union {...}` anonimi e hoista
    le DEFINIZIONI inline (con `decls`) a file-scope.

    `struct { int x; int y; } p;` ha `Struct(name=None, decls=[...])`. Mnemo
    cerca i campi in `file_specs` keyed by tag; per essere registrato, la
    definizione deve apparire a file-scope. Quindi:
    1. Genera un tag sintetico `__mn_anon_struct_<N>` / `__mn_anon_union_<N>`.
    2. Aggiunge `struct <TAG> { ... };` a `ast.ext` (file-scope decl).
    3. Sostituisce la definizione inline con un riferimento `struct <TAG>`
       (Struct con decls=None).
    """
    counter = [0]

    def name_for(kind: str) -> str:
        n = counter[0]
        counter[0] += 1
        return f"__mn_anon_{kind}_{n}"

    file_scope_decls: list[c.Decl] = []

    def maybe_promote_inline(s: c.Struct | c.Union) -> None:
        """Se `s` è anonimo con decls inline, dagli un nome sintetico e sposta
        i decls a un Decl file-scope sintetico. Skip se già aveva un name
        (struct named, decls vanno gestiti normalmente da
        collect_file_typedefs_structs_unions_enums)."""
        if s.decls is None:
            return
        if s.name is not None:
            return  # già named: lascia inline (Mnemo lo registra via file_specs)
        kind = "struct" if isinstance(s, c.Struct) else "union"
        s.name = name_for(kind)
        # Crea una copia con decls per file-scope (mantiene rif inline = no decls).
        if isinstance(s, c.Struct):
            fs_su = c.Struct(name=s.name, decls=list(s.decls), coord=s.coord)
        else:
            fs_su = c.Union(name=s.name, decls=list(s.decls), coord=s.coord)
        fs_decl = c.Decl(
            name=None, quals=[], align=[], storage=[], funcspec=[],
            type=fs_su, init=None, bitsize=None, coord=s.coord,
        )
        file_scope_decls.append(fs_decl)
        # Trasforma il riferimento inline a un puro tag-ref (no decls). Mantiene
        # struct_specs registration ok e il sito locale `struct TAG var;`.
        s.decls = None

    def visit(node: c.Node | None) -> None:
        if node is None:
            return
        for attr in getattr(node, "__slots__", ()):
            if attr in ("coord", "__weakref__"):
                continue
            val = getattr(node, attr, None)
            if isinstance(val, (c.Struct, c.Union)):
                # Recurse prima (per nested anon dentro decls), poi promote.
                if val.decls is not None:
                    for d in val.decls:
                        visit(d)
                    maybe_promote_inline(val)
            elif isinstance(val, list):
                for item in val:
                    if isinstance(item, (c.Struct, c.Union)):
                        if item.decls is not None:
                            for d in item.decls:
                                visit(d)
                            maybe_promote_inline(item)
                    elif hasattr(item, "__slots__"):
                        visit(item)
            elif hasattr(val, "__slots__"):
                visit(val)

    visit(ast)
    if file_scope_decls:
        ast.ext = file_scope_decls + list(ast.ext)


def _hoist_compound_literals_in_ast(ast: c.FileAST) -> None:
    """Applica `_hoist_compound_literals` a ogni FuncDef del file."""
    for ext in ast.ext:
        if not isinstance(ext, c.FuncDef) or ext.body is None:
            continue
        decls = _hoist_compound_literals(ext)
        if not decls:
            continue
        body = ext.body
        if not isinstance(body, c.Compound):
            continue
        items = list(body.block_items or [])
        body.block_items = decls + items


def _rename_id_in_subtree(node: c.Node | None, old: str, new: str) -> None:
    """Walk shallow + sostituisce ogni `c.ID(name=old)` con `c.ID(name=new)` in-place
    sui attrs sub-Node di `node`. Non rinomina `ID` dentro `Decl` (declarator) o
    `ParamList.exprs[*].name` di sub-Decl (sarebbero scope diversi)."""
    if node is None:
        return
    for attr in getattr(node, "__slots__", ()):
        if attr in ("coord", "__weakref__"):
            continue
        val = getattr(node, attr, None)
        if isinstance(val, c.ID) and val.name == old:
            val.name = new
        elif isinstance(val, list):
            for item in val:
                if isinstance(item, c.ID) and item.name == old:
                    item.name = new
                elif hasattr(item, "__slots__"):
                    _rename_id_in_subtree(item, old, new)
        elif hasattr(val, "__slots__"):
            _rename_id_in_subtree(val, old, new)


def _hoist_static_locals(ast: c.FileAST) -> None:
    """Hoist `static int n = …;` declarations dentro le funzioni a livello file.
    Senza questo, ogni chiamata della funzione re-inizializza `n` (semantica
    locale normale) — non match gcc.

    Per ogni `static`-tagged Decl in un FuncDef body:
    1. Rinomina a `__mn_static_<func>_<name>` (univoco per funzione).
    2. Rimuove storage `static` e sposta la Decl a file-scope (ast.ext).
    3. Sostituisce ogni `ID(name)` nel body della funzione con `ID(synth)`.

    Caveat reversibilità: file-scope vars sono globali, le mutazioni dentro la
    funzione persistono tra chiamate (semantica gcc). opt-uncall su una
    funzione che muta uno static deve includerlo nel snap (file-scope memN già
    parte del layout).
    """
    new_file_decls: list[c.Decl] = []
    for ext in ast.ext:
        if not isinstance(ext, c.FuncDef) or ext.body is None:
            continue
        fname = ext.decl.name or "_"
        body = ext.body
        if not isinstance(body, c.Compound):
            continue
        items = list(body.block_items or [])
        new_items: list[c.Node] = []
        for item in items:
            if (
                isinstance(item, c.Decl)
                and item.storage
                and "static" in item.storage
                and item.name is not None
            ):
                orig = item.name
                synth = f"__mn_static_{fname}_{orig}"
                # Rinomina declname interno (TypeDecl.declname) per riflettere il
                # nuovo identificatore.
                new_type = _rename_decl_type(item.type, synth)
                new_decl = c.Decl(
                    name=synth,
                    quals=list(item.quals or []),
                    align=list(item.align or []) if item.align else [],
                    storage=[],
                    funcspec=list(item.funcspec or []),
                    type=new_type,
                    init=item.init,
                    bitsize=item.bitsize,
                    coord=item.coord,
                )
                new_file_decls.append(new_decl)
                # Sostituisci references nel body (escluso questa Decl che
                # rimuoviamo) — rinominali a `synth`.
                _rename_id_in_subtree(body, orig, synth)
                # Non includere `item` in new_items: lo trasloca a file-scope.
                continue
            new_items.append(item)
        body.block_items = new_items
    if new_file_decls:
        # File-scope Decl in testa: precede tutte le FuncDef per ordine init.
        ast.ext = new_file_decls + list(ast.ext)


def lower_file_to_program(
    ast: c.FileAST,
    *,
    main_argc: int = 0,
    ptr_pool_size: int = 4,
    layout: ProgramMemLayout | None = None,
    physical_mem_cells: int | None = None,
    opt_uncall_user_calls: bool = False,
) -> Program:
    if not (1 <= ptr_pool_size <= PTR_POOL_MAX):
        raise MnemoCompileError(
            f"ptr_pool_size deve essere tra 1 e {PTR_POOL_MAX}, non {ptr_pool_size}"
        )
    # Note: `_hoist_compound_literals_in_ast(ast)` deve essere chiamato DAL caller
    # (compile.py) PRIMA di `compute_program_mem_layout`, altrimenti i Decl sintetici
    # non sono nel layout.
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
    mutex_keys = collect_mutex_channel_keys(ast, file_specs, file_td)
    fs_pi = collect_file_scope_kairos_pi_channels(ast)
    fs_pi_set = frozenset(fs_pi)
    fs_ch_order = file_scope_channel_order(mutex_keys, fs_pi)
    # `*__lane` (campo `lane` di mps_t single-channel): prefisso `__mn_kch_` per evitare
    # le semantiche mailbox `__mn_mtx_*` della VM (la mailbox sovrascrive — qui serve FIFO).
    file_scope_channel_kairos = {
        k: (
            f"__mn_kch_{k}"
            if (k in fs_pi_set or k.endswith("__lane"))
            else f"__mn_mtx_{k}"
        )
        for k in fs_ch_order
    }

    if layout is None:
        layout = compute_program_mem_layout(ast, ptr_pool_size)
    phys = physical_mem_cells if physical_mem_cells is not None else layout.total_cells
    if phys < layout.total_cells:
        raise MnemoCompileError(
            f"physical_mem_cells ({phys}) < layout.total_cells ({layout.total_cells})"
        )

    user_fn_specs: list[tuple[c.FuncDef, int]] = []
    for ext in ast.ext:
        if isinstance(ext, c.FuncDef) and ext.decl.name != "main":
            fname = ext.decl.name or ""
            if fname in MPS_INLINE_AT_CALLSITE:
                continue
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
            user_fn_specs.append((ext, fn_phys))

    par2_workers_all = infer_par2_workers_all(ast)

    def _lower_one_user(
        ext_phys: tuple[c.FuncDef, int],
        *,
        opt_uc: bool,
        uc_excl: frozenset[str],
        ch_targets: frozenset[str] = frozenset(),
        touches: dict[str, frozenset[int]] | None = None,
    ):
        ext, fn_phys = ext_phys
        return _lower_user_function(
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
            file_scope_channel_order=fs_ch_order,
            file_scope_channel_kairos=file_scope_channel_kairos,
            opt_uncall_user_calls=opt_uc,
            uncall_excluded_via_vm_targets=uc_excl,
            channel_using_targets=ch_targets,
            par2_workers=par2_workers_all,
            callee_mem_touches=touches,
        )

    user_fns_probe = [_lower_one_user(s, opt_uc=False, uc_excl=frozenset()) for s in user_fn_specs]
    probe_by_name = {fn.name: fn for fn in user_fns_probe}
    bad_uncall_via_vm = _uncall_excluded_transitive_closure(probe_by_name)
    mem_touches = _compute_callee_mem_touches(probe_by_name, layout.total_cells)
    channel_targets: frozenset[str] = frozenset(
        n for n, f in probe_by_name.items() if _user_procedure_uses_channels(f)
    )
    if opt_uncall_user_calls:
        user_fns = [
            _lower_one_user(s, opt_uc=True, uc_excl=bad_uncall_via_vm,
                            ch_targets=channel_targets, touches=mem_touches)
            for s in user_fn_specs
        ]
    else:
        user_fns = [
            _lower_one_user(s, opt_uc=False, uc_excl=frozenset(),
                            ch_targets=channel_targets, touches=mem_touches)
            for s in user_fn_specs
        ]

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
        opt_uncall_user_calls=opt_uncall_user_calls,
        uncall_excluded_via_vm_targets=bad_uncall_via_vm,
        channel_using_targets=channel_targets,
        par2_workers=par2_workers_all,
        callee_mem_touches=mem_touches,
    )
    _bind_ctx_layout(ctx, layout, "main")
    ctx.file_scope_channel_order = fs_ch_order
    ctx.channel_decl_order = list(fs_ch_order)
    ctx.channel_kairos.update(file_scope_channel_kairos)
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

    # Inizializza variabili file-scope `int g = K;` (e static locals hoisted)
    # con K != 0. Le celle sono già zero per default, quindi `mem += K` setta
    # il valore iniziale. Per static locals (semantica gcc): l'init avviene
    # una sola volta, alla partenza del programma — equivalente a init main.
    # Lo stesso vale per array a file-scope `int arr[N] = {…};`.
    for ext in ast.ext:
        if not isinstance(ext, c.Decl) or ext.init is None:
            continue
        if isinstance(ext.type, c.FuncDecl):
            continue
        # Union a file-scope con InitList: scrive sulla cella `varname` (union
        # = single cell con field overlap). Solo Constant int.
        ut = _union_tag_for_decl_type(ext.type, ctx)
        if ut is not None and isinstance(ext.init, c.InitList):
            if not isinstance(ext.type, c.TypeDecl) or ext.type.declname is None:
                continue
            varname = str(ext.type.declname)
            exprs = ext.init.exprs
            if not exprs:
                continue
            init_expr = exprs[0]
            if isinstance(init_expr, c.NamedInitializer):
                init_expr = init_expr.expr
            v = _int_constant_value(init_expr)
            if v is not None and v != 0:
                instrs.append(IAddEq(_phys(ctx, varname), Imm(v)))
            continue
        # Struct a file-scope con InitList: emit IAddEq sui campi.
        st_tag = _struct_tag_for_decl_type(ext.type, ctx)
        if st_tag is not None and isinstance(ext.init, c.InitList):
            if not isinstance(ext.type, c.TypeDecl) or ext.type.declname is None:
                continue
            varname = str(ext.type.declname)
            fields = ctx.struct_specs.get(st_tag)
            if not fields:
                continue
            field_order = [
                fn for fn, fty in fields
                if not _type_node_is_pthread_mutex(fty, ctx.typedef_map)
            ]
            has_named = any(
                isinstance(e, c.NamedInitializer) for e in ext.init.exprs
            )
            pos = 0
            for e in ext.init.exprs:
                if isinstance(e, c.NamedInitializer):
                    if len(e.name) != 1 or not isinstance(e.name[0], c.ID):
                        continue
                    fname = e.name[0].name
                    if fname not in field_order:
                        continue
                    v = _int_constant_value(e.expr)
                    if v is not None and v != 0:
                        loc = _struct_field_local(varname, fname)
                        instrs.append(IAddEq(_phys(ctx, loc), Imm(v)))
                    pos = field_order.index(fname) + 1
                else:
                    if pos >= len(field_order):
                        break
                    v = _int_constant_value(e)
                    if v is not None and v != 0:
                        loc = _struct_field_local(varname, field_order[pos])
                        instrs.append(IAddEq(_phys(ctx, loc), Imm(v)))
                    pos += 1
                _ = has_named
            continue
        # Array a file-scope con InitList: emit IAddEq cell-by-cell.
        if isinstance(ext.type, c.ArrayDecl):
            ap = _try_parse_array_decl(ext, ctx)
            if ap is None or not isinstance(ext.init, c.InitList):
                continue
            arr_name, dims, _esz = ap
            tot = int(math.prod(dims))
            if len(dims) == 1:
                dense = _array_init_dense_1d(ext.init, tot)
            else:
                dense = _array_init_dense_nd(ext.init, list(dims))
            for j, el in enumerate(dense):
                if el is None:
                    continue
                v = _int_constant_value(el)
                if v is None or v == 0:
                    continue
                cell_name = _array_elem_local(arr_name, j)
                pn = _phys(ctx, cell_name)
                instrs.append(IAddEq(pn, Imm(v)))
            continue
        # Solo scalar int / typedef-of-int / enum con init Constant non-zero.
        nm = _scalar_int_decl_name_for_init(ext, file_td)
        if nm is None:
            continue
        init_expr = ext.init
        val: int | None = _int_constant_value(init_expr)
        if val is None and isinstance(init_expr, c.ID):
            val = ctx.enum_constants.get(init_expr.name)
        if val is None or val == 0:
            continue
        pn = _phys(ctx, nm)
        instrs.append(IAddEq(pn, Imm(val)))

    _scope_init_params(ctx, [name for name, _role in main_param_setup])
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
