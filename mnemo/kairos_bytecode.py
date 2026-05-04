"""Kairos: sorgente .kairos → bytecode testuale; bundling eseguibile C + libvm.so."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from mnemo.errors import MnemoCompileError

# Eseguito nel venv Kairos: stdin = sorgente Kairos completo (eventuale pragma Mnemo in testa).
_COMPILE_TO_BYTECODE_PY = r"""
import sys
sys.path.insert(0, sys.argv[1])
from src.frontend.lexer import lexer
from src.frontend.parser import parser, run_static_checks
from src.frontend.bytecode import ByteCode_Compiler
from src.frontend.errors import KairosCompileError

_K = "// KAIROS_ALLOW_PAR_SHARED_INT"

def _strip(source):
    lines = source.splitlines()
    if lines and lines[0].strip() == _K:
        body = lines[1:]
        return ("\n".join(body) + ("\n" if body else ""), True)
    return source, False

source = sys.stdin.read()
source, skip = _strip(source)
try:
    ast = parser.parse(source, lexer=lexer)
    if ast is None:
        raise KairosCompileError("PARSER", "compilazione interrotta: AST non generato")
    run_static_checks(ast, check_par_int_race=not skip)
    c = ByteCode_Compiler()
    c.process(ast)
except KairosCompileError as exc:
    print(exc, file=sys.stderr)
    sys.exit(1)
except Exception as exc:
    print(f"[COMPILER] errore interno: {exc}", file=sys.stderr)
    sys.exit(1)

lines = []
while not c.queue.empty():
    _phys, src_tag, instr = c.queue.get()
    lines.append(f"{src_tag:<6}  {instr}")
sys.stdout.write("\n".join(lines) + "\n")
"""

_BUNDLE_MAIN_C = Path(__file__).resolve().parent / "mnemo_bundle_main.c"


def resolve_kairos_root() -> Path | None:
    roots: list[Path] = []
    for key in ("KAIROS_ROOT", "MNEMO_KAIROS_ROOT"):
        v = os.environ.get(key)
        if v:
            roots.append(Path(v).resolve())
    here = Path(__file__).resolve().parent
    roots.append(here.parents[1] / "kairos")
    for root in roots:
        if (root / "src" / "frontend" / "bytecode.py").is_file():
            return root
    return None


def kairos_venv_python(kairos_root: Path) -> Path | None:
    for cand in (
        kairos_root / "venv" / "bin" / "python",
        kairos_root / "venv" / "Scripts" / "python.exe",
    ):
        if cand.is_file():
            return cand
    return None


def libvm_path(kairos_root: Path) -> Path:
    return kairos_root / "build" / "libvm.so"


def kairos_source_to_bytecode(source: str, kairos_root: Path) -> str:
    py = kairos_venv_python(kairos_root)
    if not py:
        raise MnemoCompileError(
            "repo Kairos senza venv Python (atteso venv/bin/python). "
            "Crea il venv nel repo Kairos o imposta KAIROS_ROOT."
        )
    env = {**os.environ, "PYTHONPATH": str(kairos_root)}
    r = subprocess.run(
        [str(py), "-c", _COMPILE_TO_BYTECODE_PY, str(kairos_root)],
        input=source,
        capture_output=True,
        text=True,
        env=env,
        cwd=str(kairos_root),
        check=False,
    )
    if r.returncode != 0:
        err = (r.stderr or r.stdout or "").strip()
        raise MnemoCompileError(
            f"compilazione Kairos → bytecode fallita:\n{err or '(nessun messaggio)'}"
        )
    return r.stdout


def _c_escape_chunk(text: str) -> str:
    """Escape per letterale stringa C (UTF-8 come byte in \\ooo se non ASCII stampabile)."""
    parts: list[str] = []
    for ch in text:
        o = ord(ch)
        if ch == "\\":
            parts.append("\\\\")
        elif ch == '"':
            parts.append('\\"')
        elif ch == "\n":
            parts.append("\\n")
        elif ch == "\r":
            parts.append("\\r")
        elif ch == "\t":
            parts.append("\\t")
        elif 32 <= o < 127:
            parts.append(ch)
        else:
            parts.append("\\%03o" % o)
    return "".join(parts)


def bytecode_as_c_translation_unit(bytecode: str) -> str:
    """Genera mnemo_embedded_bytecode[] come catena di letterali C (UTF-8)."""
    lines_out = [
        "/* Generato da mnemo — bytecode Kairos incorporato. */",
        "const char mnemo_embedded_bytecode[] =",
    ]
    if not bytecode:
        lines_out.append('  "";')
        return "\n".join(lines_out) + "\n"
    if not bytecode.endswith("\n"):
        bytecode += "\n"
    for chunk in bytecode.splitlines(keepends=True):
        lines_out.append(f'  "{_c_escape_chunk(chunk)}"')
    lines_out.append("  ;")
    return "\n".join(lines_out) + "\n"


def _find_cc() -> str:
    cc = os.environ.get("CC")
    if cc:
        return cc
    for cand in ("gcc", "clang"):
        found = shutil.which(cand)
        if found:
            return found
    raise MnemoCompileError(
        "nessun compilatore C trovato (imposta CC o installa gcc/clang nel PATH)."
    )


def build_native_standalone(
    *,
    kairos_source: str,
    output_exe: Path,
    kairos_root: Path,
    verbose: bool = False,
) -> None:
    """
    Eseguibile nativo che incorpora il bytecode e chiama vm_run_from_string_quiet.
    Copia ``libvm.so`` accanto all'eseguibile; serve ``-Wl,-rpath,$ORIGIN``.
    """
    vm = libvm_path(kairos_root)
    if not vm.is_file():
        raise MnemoCompileError(
            f"manca {vm}: nel repo Kairos esegui `make build-release` "
            f"(serve anche vm_run_from_string_quiet in questa versione di libvm)."
        )
    if not _BUNDLE_MAIN_C.is_file():
        raise MnemoCompileError(f"manca stub C: {_BUNDLE_MAIN_C}")

    bytecode = kairos_source_to_bytecode(kairos_source, kairos_root)
    output_exe = output_exe.resolve()
    output_exe.parent.mkdir(parents=True, exist_ok=True)

    cc = _find_cc()
    with tempfile.TemporaryDirectory(prefix="mnemo-native-") as td_raw:
        td = Path(td_raw)
        embedded_path = td / "mnemo_embedded_bytecode.c"
        embedded_path.write_text(bytecode_as_c_translation_unit(bytecode), encoding="utf-8")
        lib_dir = str((kairos_root / "build").resolve())
        # $ORIGIN è interpretato dal dynamic linker, non dalla shell.
        cmd = [
            cc,
            "-O2",
            "-Wall",
            "-Wextra",
            "-o",
            str(output_exe),
            str(_BUNDLE_MAIN_C),
            str(embedded_path),
            f"-L{lib_dir}",
            "-lvm",
            "-Wl,-rpath,$ORIGIN",
            "-pthread",
        ]
        if verbose:
            print(f"mnemo: {' '.join(cmd)}", file=sys.stderr)
        r = subprocess.run(cmd, cwd=str(output_exe.parent), check=False, capture_output=True, text=True)
        if r.returncode != 0:
            err = (r.stderr or r.stdout or "").strip()
            raise MnemoCompileError(
                f"link dell'eseguibile fallito:\n{err or '(nessun output)'}"
            )

    lib_dest = output_exe.parent / "libvm.so"
    shutil.copy2(vm, lib_dest)
    try:
        os.chmod(output_exe, os.stat(output_exe).st_mode | 0o111)
    except OSError:
        pass
