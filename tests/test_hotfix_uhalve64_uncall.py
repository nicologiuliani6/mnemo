"""Regression: `__mn_uhalve64` uncall-ata dall'esterno (pattern try/rollback).

Storicamente il dimezzamento unsigned conteneva una coppia call+uncall di
`__mn_divmod_nonneg_fast` annidata in un if, che si corrompeva quando l'intera
chiamata veniva invertita da un contesto esterno (try/rollback che fa
rollback, es. maze_backtrack.c). Ora `__mn_uhalve64` è scritta con operazioni
native e non chiama nulla; il test resta come guardia: costruisce un .kairos
minimo dal sorgente CORRENTE di mnemo/lib/bits.kairos e fa
`call __mn_uhalve64(...); uncall __mn_uhalve64(...)` dall'esterno, che deve
completare pulito con q=2 r=1 (5 >> 1).
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
        bits = _extract_procs(os.path.join(ROOT, "mnemo/lib/bits.kairos"), {"__mn_uhalve64"})
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
        return bits + "\n" + main

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
