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
from mnemo.compile import INVERTIBILITY_MARK, compile_c_to_kairos, write_kairos_next_to_c
from mnemo.kairos_bytecode import build_native_standalone, installed_kairos_exe, resolve_kairos_root


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
    parser = argparse.ArgumentParser(
        prog="mnemo",
        description="Mnemo: reversible C → Kairos. `mnemo file.c` compiles and runs (same as `mnemo run file.c`).",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_dump = sub.add_parser("dump-ir", help="print an example IR")
    p_dump.set_defaults(handler=_cmd_dump_ir)

    p_k = sub.add_parser("emit-kairos", help="print an example .kairos on stdout")
    p_k.set_defaults(handler=_cmd_emit_kairos)

    p_c = sub.add_parser(
        "compile",
        help="compile .c → native executable (bytecode in .rodata + libvm.so next to it; no Python)",
    )
    p_c.add_argument("input", help="C source file")
    p_c.add_argument(
        "-o",
        "--output",
        help="executable path (default: the .c stem, without extension, in the same folder)",
        default=None,
    )
    p_c.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="print the gcc command and the generated paths on stderr",
    )
    p_c.add_argument(
        "--main-argc",
        type=int,
        default=None,
        metavar="N",
        help="overrides // mnemo-main-argc (default from the source: 0 if the directive is missing; N>=0)",
    )
    p_c.add_argument(
        "--keep-kairos",
        action="store_true",
        help="also write stem.kairos next to the .c (the Kairos source)",
    )
    p_c.add_argument(
        "--opt-uncall-user-calls",
        action="store_true",
        help=(
            "on calls main→f defined in the .c (f not recursive): after the call, "
            "XOR-copy the result (int), then uncall; void → call + uncall"
        ),
    )
    p_c.add_argument(
        "--check-invertibility",
        action="store_true",
        help=(
            "move the body of the C main into procedure `__main__` with hist+scratch stacks; "
            "Kairos `main` does `call __main__ ; uncall __main__` to check "
            "that the WHOLE program is 100%% reversible"
        ),
    )
    p_c.set_defaults(handler=_cmd_compile)

    p_dk = sub.add_parser(
        "dump-kairos",
        help="only emit the .kairos source (text) from a .c, without linking the VM",
    )
    p_dk.add_argument("input", help="C source file")
    p_dk.add_argument(
        "-o",
        "--output",
        help=".kairos file (default: same name as the .c in the same folder)",
        default=None,
    )
    p_dk.add_argument(
        "--stdout",
        action="store_true",
        help="print the .kairos on stdout instead of writing it to disk",
    )
    p_dk.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="print the path of the written file on stderr",
    )
    p_dk.add_argument(
        "--main-argc",
        type=int,
        default=None,
        metavar="N",
        help="as for compile",
    )
    p_dk.add_argument(
        "--opt-uncall-user-calls",
        action="store_true",
        help="as for compile",
    )
    p_dk.add_argument(
        "--check-invertibility",
        action="store_true",
        help="as for compile",
    )
    p_dk.set_defaults(handler=_cmd_dump_kairos)

    p_r = sub.add_parser(
        "run",
        help="compile .c → .kairos and run it in the VM (prefers ../kairos/venv, like the Makefile)",
    )
    p_r.add_argument("input", help="C source file")
    p_r.add_argument(
        "--kairos",
        default=None,
        help="Kairos executable to use (default: Kairos repository, then env MNEMO_KAIROS, then 'kairos')",
    )
    p_r.add_argument(
        "--main-argc",
        type=int,
        default=None,
        metavar="N",
        help="as for compile: overrides argc (without the flag: 0 or the // mnemo-main-argc value)",
    )
    p_r.add_argument(
        "--opt-uncall-user-calls",
        action="store_true",
        help="as for compile",
    )
    p_r.add_argument(
        "--check-invertibility",
        action="store_true",
        help="as for compile",
    )
    p_r.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="print the command used and the VM exit code on stderr",
    )
    p_r.add_argument(
        "--vm-dump",
        action="store_true",
        help="also print the VM dump block (after «=== VM dump ===»); default: no",
    )
    p_r.add_argument(
        "--vm-stats",
        action="store_true",
        help="after the VM dump print mean_abs and max_abs of the remaining int cells",
    )
    p_r.add_argument(
        "--auto",
        action="store_true",
        help="choose --opt-uncall-user-calls automatically from the .c content "
        "(cells, bitwise). Prints the decision on stderr. An explicit flag wins.",
    )
    p_r.set_defaults(handler=_cmd_run)

    # Come `kairos file.kairos`: `mnemo file.c [opzioni]` equivale a `mnemo run file.c`.
    argv = list(sys.argv[1:] if argv is None else argv)
    first = next((a for a in argv if not a.startswith("-")), None)
    if first is not None and first not in sub.choices and "-h" not in argv and "--help" not in argv:
        argv.insert(0, "run")
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
            opt_uncall_user_calls=args.opt_uncall_user_calls,
            check_invertibility=args.check_invertibility,
        )
    except MnemoCompileError as e:
        print(f"mnemo: {e}", file=sys.stderr)
        sys.exit(1)
    kroot = resolve_kairos_root()
    kexe = None if kroot else installed_kairos_exe()
    if not kroot and not kexe:
        print(
            "mnemo: Kairos not found. Install the kairos package, set KAIROS_ROOT "
            "or clone kairos next to mnemo.",
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
            kairos_exe=kexe,
            verbose=args.verbose,
        )
    except MnemoCompileError as e:
        print(f"mnemo: {e}", file=sys.stderr)
        sys.exit(1)
    if args.keep_kairos:
        written_k = write_kairos_next_to_c(args.input, out)
        if args.verbose:
            print(f"mnemo: also written {written_k}", file=sys.stderr)
    if args.verbose:
        print(
            f"mnemo: executable {exe_path} (and libvm.so in the same directory)",
            file=sys.stderr,
        )


def _cmd_dump_kairos(args: argparse.Namespace) -> None:
    try:
        out = compile_c_to_kairos(
            args.input,
            main_argc=args.main_argc,
            opt_uncall_user_calls=args.opt_uncall_user_calls,
            check_invertibility=args.check_invertibility,
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
        print(f"mnemo: wrote {written}", file=sys.stderr)


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
    # Rimuovi solo i newline che precedono il separatore di dump, NON gli spazi
    # finali dell'output reale (`printf("%d ", …)` deve conservare il trailing
    # space, gcc-equivalente).
    out = head_filtered.rstrip("\n") + ("\n" if head_filtered.strip() else "")
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
    il dump della VM — come `make run` nel Makefile. Altrimenti l'app installata `kairos`.
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
    if getattr(args, "auto", False):
        from mnemo.compile import auto_select_optimizations
        try:
            ou, reason = auto_select_optimizations(args.input)
        except MnemoCompileError as e:
            print(f"mnemo: {e}", file=sys.stderr)
            sys.exit(1)
        print(f"mnemo: {reason}", file=sys.stderr)
        # Il flag esplicito dell'utente vince: --auto abilita solo se non chiesto.
        if not args.opt_uncall_user_calls:
            args.opt_uncall_user_calls = ou
    try:
        out = compile_c_to_kairos(
            args.input,
            main_argc=args.main_argc,
            opt_uncall_user_calls=args.opt_uncall_user_calls,
            check_invertibility=args.check_invertibility,
        )
    except MnemoCompileError as e:
        print(f"mnemo: {e}", file=sys.stderr)
        sys.exit(1)
    out_path = write_kairos_next_to_c(args.input, out)
    out_abs = os.path.abspath(out_path)

    cmd: list[str]
    cwd: str | None = None

    if args.kairos is not None:
        exe = args.kairos
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
            cmd = [installed_kairos_exe() or "kairos", out_abs]

    run_env = os.environ.copy()
    if getattr(args, "vm_stats", False):
        run_env["KAIROS_VM_STATS"] = "1"
        # Propaga il flag al wrapper kairos (parse di sys.argv per --vm-stats).
        cmd = list(cmd) + ["--vm-stats"]
    # Output in REALTIME: la VM (libvm.so printf C + wrapper Python) usa
    # block-buffering quando stdout è una pipe → l'output uscirebbe a blocchi
    # (tutto a fine esecuzione). Forziamo line-buffering: `stdbuf -oL` (LD_PRELOAD
    # sui flussi stdio, copre la printf C di libvm) + PYTHONUNBUFFERED (lato wrapper).
    run_env["PYTHONUNBUFFERED"] = "1"
    _stdbuf = shutil.which("stdbuf")
    if _stdbuf and not args.vm_dump:
        cmd = [_stdbuf, "-oL"] + list(cmd)

    if args.verbose:
        print(f"mnemo: run {cmd!r} cwd={cwd!r}", file=sys.stderr)
    # Streaming line-by-line: l'output del programma (printf) esce in REALTIME
    # mentre la VM gira, invece di apparire tutto a fine esecuzione. Il filtro
    # (rimozione del blocco «=== VM dump ===», soppressione di `__mn_exit:N`,
    # estrazione dell'exit code, stats in coda con --vm-stats) è applicato a
    # flusso. `--vm-dump` stampa tutto raw. stderr non-verbose scartato, verbose
    # ereditato (stream live al terminale).
    want_stats = getattr(args, "vm_stats", False)
    exit_re = re.compile(r"^__mn_exit:\s*(-?\d+)\s*$")
    try:
        proc = subprocess.Popen(
            cmd,
            cwd=cwd,
            env=run_env,
            stdout=subprocess.PIPE,
            stderr=(None if args.verbose else subprocess.DEVNULL),
            text=True,
            bufsize=1,
        )
    except FileNotFoundError:
        print(
            "mnemo: Kairos not found. Options:\n"
            "  - install the kairos package (Kairos releases)\n"
            "  - or: clone kairos next to mnemo (../kairos with venv)\n"
            "  - or: export KAIROS_ROOT=/path/to/kairos/repo\n"
            "  - or: mnemo run --kairos /path/to/kairos file.c",
            file=sys.stderr,
        )
        sys.exit(127)

    exit_out: int | None = None
    in_dump = False
    after_mark = False
    dump_tail: list[str] = []
    pending_blanks: list[str] = []   # trailing newline holdback (rstrip pre-dump)
    assert proc.stdout is not None
    for line in proc.stdout:
        if args.vm_dump:
            sys.stdout.write(line)
            continue
        if in_dump or after_mark:
            dump_tail.append(line)
            if "=== VM dump ===" in line:
                in_dump = True
            continue
        if line.startswith(INVERTIBILITY_MARK + ":"):
            # --check-invertibility: da qui l'uncall ristampa l'output al contrario.
            after_mark = True
            continue
        if "=== VM dump ===" in line:
            in_dump = True
            dump_tail.append(line)
            continue
        m = exit_re.match(line.rstrip("\n"))
        if m:
            if exit_out is None:
                exit_out = int(m.group(1))
            continue  # `__mn_exit:N` non fa parte dell'output mostrato
        if line.strip() == "":
            pending_blanks.append(line)  # non stampare blank finali pre-dump
            continue
        if pending_blanks:
            sys.stdout.write("".join(pending_blanks))
            pending_blanks = []
        sys.stdout.write(line)
        sys.stdout.flush()
    proc.wait()
    # Stats Kairos (dal blocco dump bufferizzato) in coda, se richiesto.
    if want_stats and not args.vm_dump:
        tail = "".join(dump_tail)
        marker = "=== VM stats ==="
        if marker in tail:
            stats_block = marker + tail.split(marker, 1)[1]
            sys.stdout.write(stats_block if stats_block.endswith("\n") else stats_block + "\n")
    sys.stdout.flush()
    if args.verbose:
        print(
            f"mnemo: VM exit {proc.returncode}"
            + (f", main exit {exit_out}" if exit_out is not None else ""),
            file=sys.stderr,
        )
    if proc.returncode != 0:
        sys.exit(proc.returncode)
    if exit_out is not None:
        sys.exit(exit_out)
    sys.exit(0)


if __name__ == "__main__":
    main()
