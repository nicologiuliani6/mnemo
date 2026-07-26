"""Regression: hotfix-divmod-nonneg-fast-bug.

`__mn_uhalve64` (lib/bits.kairos) computes an unsigned 64-bit halving and, in
its "x != INT64_MIN" branch, used to do:

    call __mn_divmod_nonneg_fast(ab, two, qab, rab, ...)
    ... accumulate qab/rab into q/r ...
    uncall __mn_divmod_nonneg_fast(ab, two, qab, rab, ...)

with that whole call+uncall pair nested inside an if/else (the
`is_min == 1` branch selector). That is fine as long as __mn_uhalve64 is only
ever CALLED forward — but __mn_shr_into (used for unsigned `>>` on values
with the high bit set) invokes __mn_uhalve64 from inside a loop, and if the
ENTIRE caller ends up being uncalled from an even more external context (a
`try/rollback` that rolls back — e.g. tests/c/examples_advanced/
maze_backtrack.c doing `grid[ny][nx]` via bitwise pool-dispatch inside a
try/rollback), the VM has to invert that nested call+uncall pair a second
time. That corrupts the __mn_divmod_nonneg_fast frame's local state:

    [VM] DELOCAL: valore finale errato! (frame=__mn_divmod_nonneg_fast
         var=doable, atteso=0, trovato=1152921504606846976, c_val=0)

(1152921504606846976 == 2**60, a leftover MSB-first loop weight) or, for
other inputs, "[VM] POP: stack vuoto!". This was never exercised by the
existing suite because no other example calls __mn_divmod_nonneg_fast (or
anything built on it) from inside a try/rollback body that actually rolls
back.

Fix: extracted the "x != INT64_MIN" branch content into its own procedure
(`__mn_uhalve64_general`), called with a single `call` (no matching
`uncall`) from __mn_uhalve64's if/else — same "flatten nested if into a
procedure boundary" workaround already used by `__mn_and_into`/`__mn_or_into`
in lib/bits.kairos for the analogous "nested if" VM uncall bug.

This test builds a minimal standalone .kairos program straight from the
CURRENT lib/helpers.kairos, lib/divmod.kairos and lib/bits.kairos sources
(so it tracks future edits instead of a frozen copy), and does exactly the
`call __mn_uhalve64(...); uncall __mn_uhalve64(...)` pattern that a rolled
back try/rollback performs automatically. Before the fix this reproduces the
DELOCAL error above; after the fix it must complete cleanly with q=2 r=1
(5 >> 1 == 2 remainder 1).
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_PROC_RE = re.compile(r"procedure\s+(\w+)\s*\(")


def _extract_procs(path: str, names: set[str]) -> str:
    """Estrae dal file .kairos i corpi delle procedure con nome in `names`,
    verbatim (dal `procedure NAME(` fino alla riga prima della prossima
    `procedure`)."""
    with open(path, encoding="utf-8") as f:
        lines = f.read().split("\n")
    out: list[str] = []
    i, n = 0, len(lines)
    found: set[str] = set()
    while i < n:
        m = _PROC_RE.match(lines[i])
        if m and m.group(1) in names:
            start = i
            found.add(m.group(1))
            i += 1
            while i < n and not _PROC_RE.match(lines[i]):
                i += 1
            out.append("\n".join(lines[start:i]))
        else:
            i += 1
    missing = names - found
    if missing:
        raise AssertionError(f"{path}: procedure non trovate: {sorted(missing)}")
    return "\n\n".join(out)


def _resolve_kairos_python(kairos_root: str) -> str | None:
    py = os.path.join(kairos_root, "venv", "bin", "python")
    return py if os.path.isfile(py) else None


def _find_kairos_root() -> str | None:
    for key in ("KAIROS_ROOT", "MNEMO_KAIROS_ROOT"):
        v = os.environ.get(key)
        if v and _resolve_kairos_python(v):
            return v
    sibling = os.path.join(os.path.dirname(ROOT), "kairos")
    if _resolve_kairos_python(sibling):
        return sibling
    return None


class TestHotfixUhalve64Uncall(unittest.TestCase):
    """`__mn_uhalve64` deve restare correttamente invertibile quando l'INTERA
    call viene uncall-ata dall'esterno (pattern try/rollback)."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.kairos_root = _find_kairos_root()
        if cls.kairos_root is None:
            raise unittest.SkipTest(
                "Kairos VM non trovata (imposta KAIROS_ROOT o clona kairos "
                "accanto a mnemo)"
            )
        cls.kairos_python = _resolve_kairos_python(cls.kairos_root)

    def _build_fixture(self) -> str:
        helpers = _extract_procs(
            os.path.join(ROOT, "lib/helpers.kairos"), {"__mn_move_int"}
        )
        divmod_ = _extract_procs(
            os.path.join(ROOT, "lib/divmod.kairos"), {"__mn_divmod_nonneg_fast"}
        )
        bits = _extract_procs(
            os.path.join(ROOT, "lib/bits.kairos"),
            {"__mn_uhalve64_general", "__mn_uhalve64"},
        )
        main = """
procedure main()
    local int x = 0
    x += 5
    local int q = 0
    local int r = 0
    local stack __mn_hist = nil
    local stack __mn_scratch = nil
    call __mn_uhalve64(x, q, r, __mn_hist, __mn_scratch)
    show(q)
    show(r)
    uncall __mn_uhalve64(x, q, r, __mn_hist, __mn_scratch)
    delocal stack __mn_scratch = nil
    delocal stack __mn_hist = nil
    delocal int r = 0
    delocal int q = 0
    x -= 5
    delocal int x = 0
"""
        return helpers + "\n\n" + divmod_ + "\n\n" + bits + "\n" + main

    def test_uhalve64_survives_being_uncalled_from_outside(self) -> None:
        src = self._build_fixture()
        fd, path = tempfile.mkstemp(suffix=".kairos", prefix="hotfix_uhalve64_")
        try:
            with os.fdopen(fd, "w") as f:
                f.write(src)
            res = subprocess.run(
                [self.kairos_python, "-m", "src.kairos", path],
                capture_output=True,
                text=True,
                cwd=self.kairos_root,
                timeout=60,
            )
        finally:
            os.remove(path)

        combined = res.stdout + res.stderr
        self.assertNotIn(
            "[VM]", combined,
            f"errore VM (regressione hotfix-divmod-nonneg-fast-bug):\n{combined}",
        )
        self.assertEqual(res.returncode, 0, combined)
        self.assertIn("q: 2", res.stdout)
        self.assertIn("r: 1", res.stdout)


if __name__ == "__main__":
    unittest.main()
