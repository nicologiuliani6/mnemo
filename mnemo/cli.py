"""CLI Mnemo."""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from mnemo.ir import (
    Block,
    Function,
    IAddEq,
    IComment,
    IConst,
    Program,
    Imm,
    Var,
)
from mnemo.errors import MnemoCompileError
from mnemo.ir_dump import dump_program
from mnemo.emit_kairos import emit_program
from mnemo.compile import compile_c_to_kairos, write_kairos_next_to_c


def _example_program() -> Program:
    """Esempio minimo per smoke test manuale."""
    body = Block(
        "entry",
        [
            IComment("a += 3; b += a (b inizia a 0 in Kairos)"),
            IConst("a", 3),
            IAddEq("b", Var("a")),
        ],
    )
    return Program(
        functions=[
            Function(
                name="main",
                params=[],
                locals=[("int", "a"), ("int", "b")],
                blocks=[body],
            )
        ]
    )


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="mnemo", description="Mnemo IR → Kairos toolchain")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_dump = sub.add_parser("dump-ir", help="stampa IR di esempio")
    p_dump.set_defaults(handler=_cmd_dump_ir)

    p_k = sub.add_parser("emit-kairos", help="emette .kairos di esempio su stdout")
    p_k.set_defaults(handler=_cmd_emit_kairos)

    p_c = sub.add_parser("compile", help="compila un file .c in Kairos")
    p_c.add_argument("input", help="file sorgente .c")
    p_c.add_argument(
        "-o",
        "--output",
        help="file .kairos (default: stesso nome del .c nella stessa cartella)",
        default=None,
    )
    p_c.add_argument(
        "--stdout",
        action="store_true",
        help="stampa il .kairos su stdout invece di scrivere su disco",
    )
    p_c.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="stampa su stderr il path del file generato",
    )
    p_c.add_argument(
        "--main-argc",
        type=int,
        default=None,
        metavar="N",
        help="sovrascrive // mnemo-main-argc (default da sorgente: 0 se manca la direttiva; N>=0)",
    )
    p_c.add_argument(
        "--ptr-pool-size",
        type=int,
        default=4,
        metavar="N",
        help="celle pool malloc/free (__mn_mem0..__mn_mem{N-1}); default 4, max 256",
    )
    p_c.set_defaults(handler=_cmd_compile)

    p_r = sub.add_parser(
        "run",
        help="compila .c → .kairos ed esegue la VM (preferisce ../kairos/venv come nel Makefile)",
    )
    p_r.add_argument("input", help="file sorgente .c")
    p_r.add_argument(
        "--kairosapp",
        default=None,
        help="path o nome eseguibile (default: env MNEMO_KAIROSAPP o 'kairosapp')",
    )
    p_r.add_argument(
        "--main-argc",
        type=int,
        default=None,
        metavar="N",
        help="come per compile: sovrascrive argc (senza flag: 0 o valore // mnemo-main-argc)",
    )
    p_r.add_argument(
        "--ptr-pool-size",
        type=int,
        default=4,
        metavar="N",
        help="come per compile: dimensione pool puntatori",
    )
    p_r.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="stampa su stderr comando usato e codice di uscita della VM",
    )
    p_r.set_defaults(handler=_cmd_run)

    args = parser.parse_args(argv)
    args.handler(args)


def _cmd_dump_ir(_args: argparse.Namespace) -> None:
    print(dump_program(_example_program()))


def _cmd_emit_kairos(_args: argparse.Namespace) -> None:
    print(emit_program(_example_program()), end="")


def _cmd_compile(args: argparse.Namespace) -> None:
    try:
        out = compile_c_to_kairos(
            args.input,
            main_argc=args.main_argc,
            ptr_pool_size=args.ptr_pool_size,
        )
    except MnemoCompileError as e:
        print(f"mnemo: {e}", file=sys.stderr)
        sys.exit(1)
    if args.stdout:
        print(out, end="")
        return
    dest = args.output
    if dest:
        with open(dest, "w", encoding="utf-8") as f:
            f.write(out)
        written = dest
    else:
        written = write_kairos_next_to_c(args.input, out)
    if args.verbose:
        print(f"mnemo: scritto {written}", file=sys.stderr)


def _parse_main_exit_from_kairos_stdout(stdout: str) -> int | None:
    """
    Il compilatore emette `show(__mn_exit)` prima del return da main; la VM stampa
    `__mn_exit: N`. Usato da `mnemo run` come codice di uscita del processo.
    Si parsa solo l'output prima di `=== VM dump ===` così non si confonde col dump.
    """
    head, sep, _ = stdout.partition("=== VM dump ===")
    block = head if sep else stdout
    m = re.search(
        r"^(__mn_exit|__mn_mem\d+):\s*(-?\d+)\s*$",
        block,
        re.MULTILINE,
    )
    if m:
        return int(m.group(2))
    return None


def _resolve_kairos_python_runner(out_kairos_abs: str) -> tuple[list[str], str | None]:
    """
    Preferisce il runner del repo Kairos (`venv/bin/python -m src.kairos`), che stampa
    il dump della VM — come `make run` nel Makefile. Altrimenti `kairosapp` (spesso muto).
    """
    roots: list[Path] = []
    for key in ("KAIROS_ROOT", "MNEMO_KAIROS_ROOT"):
        v = os.environ.get(key)
        if v:
            roots.append(Path(v).resolve())
    # cli.py è in …/mnemo/mnemo/ → parents[0]=repo mnemo, parents[1]=cartella che contiene mnemo (es. Desktop)
    here = Path(__file__).resolve().parent
    roots.append(here.parents[1] / "kairos")

    for root in roots:
        py = root / "venv" / "bin" / "python"
        if py.is_file():
            return ([str(py), "-m", "src.kairos", out_kairos_abs], str(root))
    return ([], None)


def _cmd_run(args: argparse.Namespace) -> None:
    try:
        out = compile_c_to_kairos(
            args.input,
            main_argc=args.main_argc,
            ptr_pool_size=args.ptr_pool_size,
        )
    except MnemoCompileError as e:
        print(f"mnemo: {e}", file=sys.stderr)
        sys.exit(1)
    out_path = write_kairos_next_to_c(args.input, out)
    out_abs = os.path.abspath(out_path)

    cmd: list[str]
    cwd: str | None = None

    if args.kairosapp is not None:
        exe = args.kairosapp
        if not os.path.isabs(exe):
            found = shutil.which(exe)
            if found:
                exe = found
        cmd = [exe, out_abs]
    elif os.environ.get("MNEMO_KAIROSAPP"):
        exe = os.environ["MNEMO_KAIROSAPP"]
        if not os.path.isabs(exe):
            found = shutil.which(exe)
            if found:
                exe = found
        cmd = [exe, out_abs]
    else:
        py_cmd, cwd = _resolve_kairos_python_runner(out_abs)
        if py_cmd:
            cmd = py_cmd
        else:
            exe = "kairosapp"
            found = shutil.which(exe)
            if found:
                exe = found
            cmd = [exe, out_abs]

    if args.verbose:
        print(f"mnemo: run {cmd!r} cwd={cwd!r}", file=sys.stderr)
    try:
        r = subprocess.run(
            cmd,
            cwd=cwd,
            check=False,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        print(
            "mnemo: runner Kairos non trovato. Opzioni:\n"
            "  - clone kairos accanto a mnemo (../kairos con venv)\n"
            "  - oppure: export KAIROS_ROOT=/percorso/repo/kairos\n"
            "  - oppure: mnemo run --kairosapp /path/to/kairosapp file.c",
            file=sys.stderr,
        )
        sys.exit(127)
    if r.stdout:
        sys.stdout.write(r.stdout)
    if r.stderr:
        sys.stderr.write(r.stderr)
    exit_out = _parse_main_exit_from_kairos_stdout(r.stdout or "")
    if args.verbose:
        print(
            f"mnemo: VM exit {r.returncode}"
            + (f", main exit {exit_out}" if exit_out is not None else ""),
            file=sys.stderr,
        )
    if r.returncode != 0:
        sys.exit(r.returncode)
    if exit_out is not None:
        sys.exit(exit_out)
    sys.exit(0)


if __name__ == "__main__":
    main()
