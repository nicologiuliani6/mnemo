"""CLI Mnemo."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys

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
    p_c.set_defaults(handler=_cmd_compile)

    p_r = sub.add_parser(
        "run",
        help="compila .c → .kairos accanto al sorgente ed esegue kairosapp",
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
    p_r.set_defaults(handler=_cmd_run)

    args = parser.parse_args(argv)
    args.handler(args)


def _cmd_dump_ir(_args: argparse.Namespace) -> None:
    print(dump_program(_example_program()))


def _cmd_emit_kairos(_args: argparse.Namespace) -> None:
    print(emit_program(_example_program()), end="")


def _cmd_compile(args: argparse.Namespace) -> None:
    try:
        out = compile_c_to_kairos(args.input, main_argc=args.main_argc)
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


def _cmd_run(args: argparse.Namespace) -> None:
    try:
        out = compile_c_to_kairos(args.input, main_argc=args.main_argc)
    except MnemoCompileError as e:
        print(f"mnemo: {e}", file=sys.stderr)
        sys.exit(1)
    out_path = write_kairos_next_to_c(args.input, out)
    exe = args.kairosapp or os.environ.get("MNEMO_KAIROSAPP", "kairosapp")
    if not os.path.isabs(exe):
        found = shutil.which(exe)
        if found:
            exe = found
    try:
        r = subprocess.run([exe, out_path], check=False)
    except FileNotFoundError:
        print(
            f"mnemo: eseguibile non trovato: {exe!r} "
            f"(installa kairosapp o imposta MNEMO_KAIROSAPP)",
            file=sys.stderr,
        )
        sys.exit(127)
    sys.exit(r.returncode)


if __name__ == "__main__":
    main()
