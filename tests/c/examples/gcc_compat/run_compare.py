#!/usr/bin/env python3
"""Confronta output/exit-code tra Mnemo e GCC su tests/c/examples/gcc_compat/*.c."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
SUITE_DIR = Path(__file__).resolve().parent
MNEMO_PY = ROOT / ".venv" / "bin" / "python"
ARTIFACTS_DIR = SUITE_DIR / "artifacts"
KNOWN_DEVIATIONS_FILE = SUITE_DIR / "known_deviations.json"
CATEGORY_ALIASES: dict[str, set[str]] = {
    "all": set(),
    "types": {"enum", "unsigned", "cast", "sizeof"},
    "expr": {"expr", "bitwise", "compound"},
    "control": {"if", "loop", "switch", "control", "flow"},
    "ptr": {"ptrs", "pointers", "memory", "malloc", "params", "decl"},
    "struct_union": {"struct", "union"},
    "runtime": {"runtime", "char", "unsigned", "malloc", "memory"},
}


def run(cmd: list[str], cwd: Path) -> tuple[int, str, str]:
    proc = subprocess.run(
        cmd,
        cwd=str(cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    return proc.returncode, proc.stdout, proc.stderr


def normalize_mnemo_stdout(output: str) -> str:
    lines = output.splitlines()
    kept: list[str] = []
    for line in lines:
        if line.strip().startswith("__mn_exit:"):
            continue
        if line.strip().startswith("=== VM dump ==="):
            break
        kept.append(line)
    while kept and not kept[-1].strip():
        kept.pop()
    if not kept:
        return ""
    return "\n".join(kept) + "\n"


def discover_cases() -> list[Path]:
    return sorted(SUITE_DIR.glob("generic_*.c"))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--stop-on-first-fail",
        action="store_true",
        help="Stop immediately after the first failing test case.",
    )
    parser.add_argument(
        "--category",
        default="all",
        help="Run only one category inferred from filename (e.g. loop, struct, ptr).",
    )
    return parser.parse_args()


def infer_category(c_file: Path) -> str:
    stem = c_file.stem
    if not stem.startswith("generic_"):
        return "misc"
    parts = stem.split("_")
    if len(parts) < 2:
        return "misc"
    return parts[1]


def save_artifact(c_file: Path, reason: str, payload: dict[str, str | int]) -> None:
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    out_file = ARTIFACTS_DIR / f"{c_file.stem}.json"
    data = {"file": c_file.name, "reason": reason, **payload}
    out_file.write_text(json.dumps(data, indent=2, ensure_ascii=True) + "\n")


def clear_artifact(c_file: Path) -> None:
    out_file = ARTIFACTS_DIR / f"{c_file.stem}.json"
    if out_file.exists():
        out_file.unlink()


def load_known_deviations() -> set[str]:
    if not KNOWN_DEVIATIONS_FILE.exists():
        return set()
    data = json.loads(KNOWN_DEVIATIONS_FILE.read_text())
    if not isinstance(data, list):
        raise ValueError("known_deviations.json must be a JSON array.")
    return {str(item) for item in data}


def main() -> int:
    args = parse_args()
    if not MNEMO_PY.exists():
        print("Missing .venv/bin/python. Run `make venv` first.", file=sys.stderr)
        return 2

    if shutil.which("gcc") is None:
        print("Missing gcc in PATH.", file=sys.stderr)
        return 2

    cases = discover_cases()
    if not cases:
        print("No test cases found (generic_*.c).", file=sys.stderr)
        return 2
    if args.category != "all":
        if args.category in CATEGORY_ALIASES:
            accepted = CATEGORY_ALIASES[args.category]
            cases = [case for case in cases if infer_category(case) in accepted]
        else:
            cases = [case for case in cases if infer_category(case) == args.category]
        if not cases:
            print(f"No test cases found for category '{args.category}'.", file=sys.stderr)
            return 2

    failures = 0
    total = 0
    new_failures = 0
    known_failures = 0
    known_deviations = load_known_deviations()
    category_stats: dict[str, dict[str, int]] = {}
    for c_file in cases:
        total += 1
        category = infer_category(c_file)
        if category not in category_stats:
            category_stats[category] = {"total": 0, "fail": 0}
        category_stats[category]["total"] += 1
        exe_file = c_file.with_suffix(".gcc.out")
        print(f"== {c_file.name} ==")

        mn_rc, mn_out, mn_err = run(
            [str(MNEMO_PY), "-m", "mnemo", "run", str(c_file)],
            cwd=ROOT,
        )
        if mn_rc != 0 and not mn_out:
            print("  MNEMO RUN FAIL")
            if mn_err.strip():
                print(f"  stderr: {mn_err.strip()}")
            failures += 1
            category_stats[category]["fail"] += 1
            if c_file.name in known_deviations:
                known_failures += 1
            else:
                new_failures += 1
            save_artifact(
                c_file,
                "mnemo_run_fail",
                {"mnemo_rc": mn_rc, "mnemo_stdout": mn_out, "mnemo_stderr": mn_err},
            )
            if args.stop_on_first_fail:
                break
            continue

        gcc_build_rc, _, gcc_build_err = run(
            ["gcc", str(c_file), "-std=c11", "-Wall", "-Wextra", "-O2", "-o", str(exe_file)],
            cwd=ROOT,
        )
        if gcc_build_rc != 0:
            print("  GCC COMPILE FAIL")
            if gcc_build_err.strip():
                print(f"  stderr: {gcc_build_err.strip()}")
            failures += 1
            category_stats[category]["fail"] += 1
            if c_file.name in known_deviations:
                known_failures += 1
            else:
                new_failures += 1
            save_artifact(
                c_file,
                "gcc_compile_fail",
                {"gcc_build_rc": gcc_build_rc, "gcc_build_stderr": gcc_build_err},
            )
            if args.stop_on_first_fail:
                break
            continue
        if gcc_build_err.strip():
            print("  GCC COMPILE WARNINGS")
            print(f"  stderr: {gcc_build_err.strip()}")
            failures += 1
            category_stats[category]["fail"] += 1
            if c_file.name in known_deviations:
                known_failures += 1
            else:
                new_failures += 1
            save_artifact(
                c_file,
                "gcc_compile_warning",
                {"gcc_build_rc": gcc_build_rc, "gcc_build_stderr": gcc_build_err},
            )
            if args.stop_on_first_fail:
                break
            continue

        gcc_rc, gcc_out, gcc_err = run([str(exe_file)], cwd=ROOT)
        if gcc_err.strip():
            print(f"  gcc stderr: {gcc_err.strip()}")

        mn_out_clean = normalize_mnemo_stdout(mn_out)
        ok = True
        if mn_rc != gcc_rc:
            print(f"  EXIT CODE MISMATCH mnemo={mn_rc} gcc={gcc_rc}")
            ok = False
        if mn_out_clean != gcc_out:
            print("  STDOUT MISMATCH")
            print("  --- mnemo ---")
            sys.stdout.write(mn_out_clean)
            print("  --- gcc ---")
            sys.stdout.write(gcc_out)
            ok = False

        if ok:
            print("  OK")
            clear_artifact(c_file)
        else:
            failures += 1
            category_stats[category]["fail"] += 1
            if c_file.name in known_deviations:
                known_failures += 1
            else:
                new_failures += 1
            save_artifact(
                c_file,
                "output_mismatch",
                {
                    "mnemo_rc": mn_rc,
                    "gcc_rc": gcc_rc,
                    "mnemo_stdout": mn_out_clean,
                    "gcc_stdout": gcc_out,
                    "mnemo_stderr": mn_err,
                    "gcc_stderr": gcc_err,
                },
            )
            if args.stop_on_first_fail:
                break

    print("")
    print("Category summary:")
    for category in sorted(category_stats):
        cat_total = category_stats[category]["total"]
        cat_fail = category_stats[category]["fail"]
        cat_pass = cat_total - cat_fail
        print(f"  {category}: {cat_pass}/{cat_total} PASS")
    print("")
    if failures:
        print(f"QUALITY GATE FAILED: {failures}/{total} failing cases")
        print("Expected quality gate: no mismatch, no gcc warnings, no VM/runtime crash.")
        if known_failures:
            print(f"Known deviations hit: {known_failures}")
        if new_failures:
            print(f"New deviations introduced: {new_failures}")
        return 1

    print(f"QUALITY GATE PASSED: {total}/{total} cases")
    print("ALL TESTS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
