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
from mnemo.kairos_bytecode import build_native_standalone, resolve_kairos_root


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

    p_c = sub.add_parser(
        "compile",
        help="compila .c → eseguibile nativo (bytecode in .rodata + libvm.so accanto; niente Python)",
    )
    p_c.add_argument("input", help="file sorgente .c")
    p_c.add_argument(
        "-o",
        "--output",
        help="path dell'eseguibile (default: stesso stem del .c, senza estensione, nella stessa cartella)",
        default=None,
    )
    p_c.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="stampa su stderr il comando gcc e i path generati",
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
        default=0,
        metavar="N",
        help="celle pool malloc/free (__mn_mem0..__mn_mem{N-1}); default 0 = auto-inferito da numero di malloc/calloc nel sorgente; override solo verso l'alto se serve più capacità",
    )
    p_c.add_argument(
        "--arr-max",
        type=int,
        default=None,
        metavar="N",
        help=(
            "limite elementi totali per array (prodotto delle dimensioni); "
            "default: auto-inferito dal max array decl statico nel sorgente "
            "(minimo 1024 per decay-array params). Flag = override solo verso "
            "l'alto. NB: indicizzazione runtime emette O(N) op per accesso."
        ),
    )
    p_c.add_argument(
        "--keep-kairos",
        action="store_true",
        help="scrive anche stem.kairos accanto al .c (il sorgente Kairos testuale)",
    )
    p_c.add_argument(
        "--opt-uncall-user-calls",
        action="store_true",
        help=(
            "su chiamate da main→f definite nello .c (f non ricorsiva): dopo call, "
            "copia XOR del risultato (int) poi uncall; void → call + uncall"
        ),
    )
    p_c.add_argument(
        "--check-invertibility",
        action="store_true",
        help=(
            "isola il corpo del main C in procedura `__main__` con stack hist+scratch; "
            "in Kairos `main` fa `call __main__ ; uncall __main__` per verificare "
            "che TUTTO il programma sia reversibile al 100%"
        ),
    )
    p_c.set_defaults(handler=_cmd_compile)

    p_dk = sub.add_parser(
        "dump-kairos",
        help="emette solo il sorgente .kairos (testo) da un .c — senza linkare la VM",
    )
    p_dk.add_argument("input", help="file sorgente .c")
    p_dk.add_argument(
        "-o",
        "--output",
        help="file .kairos (default: stesso nome del .c nella stessa cartella)",
        default=None,
    )
    p_dk.add_argument(
        "--stdout",
        action="store_true",
        help="stampa il .kairos su stdout invece di scrivere su disco",
    )
    p_dk.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="stampa su stderr il path del file scritto",
    )
    p_dk.add_argument(
        "--main-argc",
        type=int,
        default=None,
        metavar="N",
        help="come per compile",
    )
    p_dk.add_argument(
        "--ptr-pool-size",
        type=int,
        default=4,
        metavar="N",
        help="come per compile",
    )
    p_dk.add_argument(
        "--arr-max",
        type=int,
        default=None,
        metavar="N",
        help="come per compile",
    )
    p_dk.add_argument(
        "--opt-uncall-user-calls",
        action="store_true",
        help="come compile",
    )
    p_dk.add_argument(
        "--check-invertibility",
        action="store_true",
        help="come compile",
    )
    p_dk.set_defaults(handler=_cmd_dump_kairos)

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
        "--arr-max",
        type=int,
        default=None,
        metavar="N",
        help="come per compile: limite elementi totali per array",
    )
    p_r.add_argument(
        "--opt-uncall-user-calls",
        action="store_true",
        help="come compile",
    )
    p_r.add_argument(
        "--check-invertibility",
        action="store_true",
        help="come compile",
    )
    p_r.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="stampa su stderr comando usato e codice di uscita della VM",
    )
    p_r.add_argument(
        "--vm-dump",
        action="store_true",
        help="stampa anche il blocco dump della VM (dopo «=== VM dump ===»); default: no",
    )
    p_r.add_argument(
        "--native-arith",
        action="store_true",
        help="abilita KAIROS_NATIVE_ARITH=1 nella VM (mul/div/bitwise O(1) in C, uncall preservato)",
    )
    p_r.add_argument(
        "--vm-stats",
        action="store_true",
        help="dopo il dump VM stampa mean_abs e max_abs dei cell int rimasti (stats post-execution)",
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
            opt_uncall_user_calls=args.opt_uncall_user_calls,
            check_invertibility=args.check_invertibility,
            arr_max=getattr(args, "arr_max", None),
        )
    except MnemoCompileError as e:
        print(f"mnemo: {e}", file=sys.stderr)
        sys.exit(1)
    kroot = resolve_kairos_root()
    if not kroot:
        print(
            "mnemo: repo Kairos non trovato. Imposta KAIROS_ROOT o clona kairos accanto a mnemo.",
            file=sys.stderr,
        )
        sys.exit(1)
    in_path = Path(args.input).resolve()
    if args.output:
        exe_path = Path(args.output).expanduser()
    else:
        exe_path = in_path.with_suffix("")
    try:
        build_native_standalone(
            kairos_source=out,
            output_exe=exe_path,
            kairos_root=kroot,
            verbose=args.verbose,
        )
    except MnemoCompileError as e:
        print(f"mnemo: {e}", file=sys.stderr)
        sys.exit(1)
    if args.keep_kairos:
        written_k = write_kairos_next_to_c(args.input, out)
        if args.verbose:
            print(f"mnemo: scritto anche {written_k}", file=sys.stderr)
    if args.verbose:
        print(
            f"mnemo: eseguibile {exe_path} (e libvm.so nella stessa directory)",
            file=sys.stderr,
        )


def _cmd_dump_kairos(args: argparse.Namespace) -> None:
    try:
        out = compile_c_to_kairos(
            args.input,
            main_argc=args.main_argc,
            ptr_pool_size=args.ptr_pool_size,
            opt_uncall_user_calls=args.opt_uncall_user_calls,
            check_invertibility=args.check_invertibility,
            arr_max=getattr(args, "arr_max", None),
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


def _stdout_without_vm_dump(stdout: str, *, keep_stats: bool = False) -> str:
    """Rimuove la sezione dump Kairos se presente (tutto da «=== VM dump ===» in poi).
    Rimuove anche `__mn_exit: N` (Kairos VM show output, gcc-equiv = exit propagato
    come codice di uscita del processo).
    Se `keep_stats`, preserva il blocco «=== VM stats ===» (lo trasla in coda)."""
    head, sep, tail = stdout.partition("=== VM dump ===")
    head_filtered = re.sub(
        r"^__mn_exit:\s*-?\d+\s*\n?", "", head, flags=re.MULTILINE
    )
    if not sep:
        return head_filtered
    out = head_filtered.rstrip() + ("\n" if head_filtered.strip() else "")
    if keep_stats:
        stats_marker = "=== VM stats ==="
        if stats_marker in tail:
            stats_block = stats_marker + tail.split(stats_marker, 1)[1]
            out = out + stats_block
            if not stats_block.endswith("\n"):
                out += "\n"
    return out


def _parse_main_exit_from_kairos_stdout(stdout: str) -> int | None:
    """
    Il compilatore emette `show(__mn_exit)` prima del return da main; la VM stampa
    `__mn_exit: N`. Usato da `mnemo run` come codice di uscita del processo.
    Si parsa solo l'output prima di `=== VM dump ===` così non si confonde col dump.
    """
    head, sep, _ = stdout.partition("=== VM dump ===")
    block = head if sep else stdout
    # Solo __mn_exit: con --opt-uncall-user-calls compaiono molte righe tipo __mn_memN (show)
    # prima del return da main — il primo match altrimenti darebbe codice di uscita errato (es. 245).
    for line in block.splitlines():
        m = re.match(r"^__mn_exit:\s*(-?\d+)\s*$", line)
        if m:
            return int(m.group(1))
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
            opt_uncall_user_calls=args.opt_uncall_user_calls,
            check_invertibility=args.check_invertibility,
            arr_max=getattr(args, "arr_max", None),
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

    run_env = os.environ.copy()
    if getattr(args, "native_arith", False):
        run_env["KAIROS_NATIVE_ARITH"] = "1"
    if getattr(args, "vm_stats", False):
        run_env["KAIROS_VM_STATS"] = "1"
        # Propaga il flag al wrapper kairos (parse di sys.argv per --vm-stats).
        cmd = list(cmd) + ["--vm-stats"]

    if args.verbose:
        print(f"mnemo: run {cmd!r} cwd={cwd!r}", file=sys.stderr)
    try:
        r = subprocess.run(
            cmd,
            cwd=cwd,
            env=run_env,
            check=False,
            stdout=subprocess.PIPE,
            stderr=(subprocess.PIPE if args.verbose else subprocess.DEVNULL),
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
    raw_stdout = r.stdout or ""
    display = (
        raw_stdout
        if args.vm_dump
        else _stdout_without_vm_dump(
            raw_stdout, keep_stats=getattr(args, "vm_stats", False)
        )
    )
    if display:
        sys.stdout.write(display)
    if r.stderr:
        sys.stderr.write(r.stderr)
    exit_out = _parse_main_exit_from_kairos_stdout(raw_stdout)
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
