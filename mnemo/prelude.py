"""
Lettura `mnemo/lib/*.kairos` per il preambolo e direttive nel sorgente C.
"""

from __future__ import annotations

import re
from pathlib import Path

from mnemo.errors import MnemoCompileError
from mnemo.ptr_pool_kairos import emit_ptr_pool_kairos

# Procedure emesse a compile-time (vedi `emit_ptr_pool_kairos`); il file `ptr_pool.kairos` in lib può essere solo un stub.
_VPTR_LIB = "ptr_pool.kairos"
_VPTR_PROCS = (
    "__mn_pool_alloc",
    "__mn_pool_store",
    "__mn_pool_load",
    "__mn_pool_free",
)

_PROC_HEAD = re.compile(
    r"^\s*procedure\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(",
    re.MULTILINE,
)


def lib_dir() -> Path:
    """Directory `mnemo/lib` (accanto al pacchetto Python `mnemo/`)."""
    return Path(__file__).resolve().parent.parent / "lib"


def lib_procedure_index() -> dict[str, str]:
    """
    Mappa nome procedura Kairos → file `.kairos` in `lib/` che la definisce.
    Usato per includere automaticamente le lib necessarie alle chiamate nel C.
    """
    root = lib_dir()
    index: dict[str, str] = {}
    for path in sorted(root.glob("*.kairos")):
        text = path.read_text(encoding="utf-8")
        for m in _PROC_HEAD.finditer(text):
            name = m.group(1)
            prev = index.get(name)
            if prev is not None and prev != path.name:
                raise MnemoCompileError(
                    f"procedura Kairos {name!r} definita due volte: {prev} e {path.name}"
                )
            index[name] = path.name
    for name in _VPTR_PROCS:
        index.setdefault(name, _VPTR_LIB)
    return index


def parse_mnemo_main_argc(source: str) -> int:
    """
    // mnemo-main-argc: N
    Valore con cui inizializzare argc per int main(int argc, ...) (default 0 se assente).
    """
    pat = re.compile(r"^\s*//\s*mnemo-main-argc:\s*(\d+)\s*$")
    for line in source.splitlines()[:80]:
        m = pat.match(line)
        if m:
            return int(m.group(1), 10)
    return 0


def parse_mnemo_skip_par_shared_mutex_check(source: str) -> bool:
    """
    // mnemo-skip-par-shared-mutex-check
    Disattiva il controllo statico «stessi slot condivisi → mutex» quando nel PAR serve
    anche attesa attiva sugli stessi campi (il mutex Mnemo è π, non un semaforo da polling).
    """
    pat = re.compile(r"^\s*//\s*mnemo-skip-par-shared-mutex-check\s*$")
    for line in source.splitlines()[:80]:
        if pat.match(line):
            return True
    return False


def load_prelude_kairos(
    lib_filenames: list[str],
    *,
    ptr_pool_size: int = 4,
    total_mem_cells: int | None = None,
    heap_base: int | None = None,
) -> str:
    """
    Genera `__mn_pool_*`. Con `heap_base` impostato (path con layout): dispatch
    statico `if slot==k` sulle celle nominate `__mn_mem0..heap_base-1`, e
    procedure `_dyn` per gli slot >= heap_base (heap VM dinamico `vm->mn_pool`,
    cresce on-demand). Senza `heap_base` (legacy): solo dispatch statico su
    `total_mem_cells`/`ptr_pool_size`.
    """
    if not lib_filenames:
        return ""
    if heap_base is not None:
        static_n = heap_base
    elif total_mem_cells is not None:
        static_n = total_mem_cells
    else:
        static_n = ptr_pool_size
    root = lib_dir()
    chunks: list[str] = []
    for lf in lib_filenames:
        if lf == _VPTR_LIB:
            chunks.append(emit_ptr_pool_kairos(static_n, heap_base).rstrip())
            continue
        path = root / lf
        if not path.is_file():
            raise FileNotFoundError(f"libreria Kairos non trovata: {path}")
        chunks.append(path.read_text(encoding="utf-8").rstrip())
    return "\n\n".join(chunks).strip() + "\n\n"
