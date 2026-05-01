"""
Lettura `mnemo/lib/*.kairos` per il preambolo e direttive nel sorgente C.
"""

from __future__ import annotations

import re
from pathlib import Path

from mnemo.errors import MnemoCompileError

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


def load_prelude_kairos(lib_filenames: list[str]) -> str:
    """Legge i file dalla cartella lib e li concatena (testo grezzo, senza main)."""
    if not lib_filenames:
        return ""
    root = lib_dir()
    chunks: list[str] = []
    for lf in lib_filenames:
        path = root / lf
        if not path.is_file():
            raise FileNotFoundError(f"libreria Kairos non trovata: {path}")
        chunks.append(path.read_text(encoding="utf-8").rstrip())
    return "\n\n".join(chunks).strip() + "\n\n"
