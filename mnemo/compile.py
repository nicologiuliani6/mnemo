"""C → .kairos: parse, lower, emit, prelude lib/."""

from __future__ import annotations

from mnemo.c_lower import (
    infer_auto_lib_files,
    infer_lib_files_from_calls,
    lower_file_to_program,
)
from mnemo.layout_collect import compute_program_mem_layout
from mnemo.c_parse import parse_c
from mnemo.emit_kairos import emit_program
from mnemo.errors import MnemoCompileError
from mnemo.prelude import lib_procedure_index, load_prelude_kairos, parse_mnemo_main_argc


def _merge_lib_lists(a: list[str], b: list[str]) -> list[str]:
    """Concatena senza duplicati, preservando l’ordine (prima `a`, poi nuovi da `b`)."""
    seen: set[str] = set()
    out: list[str] = []
    for x in a + b:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out


def compile_c_to_kairos(
    path: str, *, main_argc: int | None = None, ptr_pool_size: int = 4
) -> str:
    try:
        with open(path, encoding="utf-8") as f:
            src = f.read()
    except OSError as e:
        raise MnemoCompileError(f"file non trovato o non leggibile: {path}") from e
    ast = parse_c(path)
    proc_index = lib_procedure_index()
    lib_names = _merge_lib_lists(
        infer_auto_lib_files(ast),
        infer_lib_files_from_calls(ast, proc_index),
    )
    argc_use = parse_mnemo_main_argc(src) if main_argc is None else main_argc
    if argc_use < 0:
        raise MnemoCompileError("main_argc deve essere >= 0")
    layout = compute_program_mem_layout(ast, ptr_pool_size)
    try:
        prelude = load_prelude_kairos(
            lib_names,
            ptr_pool_size=ptr_pool_size,
            total_mem_cells=layout.total_cells,
        )
    except FileNotFoundError as e:
        raise MnemoCompileError(str(e)) from e
    prog = lower_file_to_program(
        ast,
        main_argc=argc_use,
        ptr_pool_size=ptr_pool_size,
        layout=layout,
    )
    body = emit_program(prog)
    return (prelude + body) if prelude else body


def write_kairos_next_to_c(c_path: str, content: str) -> str:
    """Scrive `stem.kairos` nella stessa directory di `c_path`. Ritorna il path scritto."""
    from pathlib import Path

    p = Path(c_path).resolve()
    out = p.with_suffix(".kairos")
    out.write_text(content, encoding="utf-8")
    return str(out)
