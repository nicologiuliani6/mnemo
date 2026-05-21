"""Parsing C con pycparser + preprocessore (gcc -E)."""

from __future__ import annotations

import os
import re
import shutil

from pycparser import CParser, c_ast, preprocess_file

from mnemo.errors import MnemoCompileError


def _fake_libc_include() -> str:
    import pycparser as _p

    return os.path.join(os.path.dirname(_p.__file__), "utils", "fake_libc_include")


_OFFSETOF_RE = re.compile(r"__builtin_offsetof\s*\(")


def _split_outer_comma(s: str) -> tuple[str, str]:
    """Split a balanced-paren expression on the top-level comma."""
    depth = 0
    for i, ch in enumerate(s):
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        elif ch == "," and depth == 0:
            return s[:i].strip(), s[i + 1:].strip()
    raise MnemoCompileError("__builtin_offsetof: virgola top-level non trovata")


def _rewrite_builtin_offsetof(text: str) -> str:
    """Convert `__builtin_offsetof(T, M)` → `__mn_offsetof_str("T", "M")`.

    Pycparser can't parse `__builtin_offsetof` or types-in-args, so we
    stringify both arguments and resolve at lower time.
    """
    out: list[str] = []
    pos = 0
    while True:
        m = _OFFSETOF_RE.search(text, pos)
        if not m:
            out.append(text[pos:])
            break
        out.append(text[pos:m.start()])
        # Find matching close paren starting after '('
        i = m.end()
        depth = 1
        n = len(text)
        while i < n and depth > 0:
            c = text[i]
            if c == "(":
                depth += 1
            elif c == ")":
                depth -= 1
                if depth == 0:
                    break
            i += 1
        if depth != 0:
            raise MnemoCompileError("__builtin_offsetof: parentesi non bilanciate")
        inner = text[m.end():i]
        type_spec, member = _split_outer_comma(inner)
        # Normalize whitespace in type_spec / member.
        type_spec = " ".join(type_spec.split())
        member = " ".join(member.split())
        out.append(
            f'__mn_offsetof_str("{type_spec}", "{member}")'
        )
        pos = i + 1
    return "".join(out)


def parse_c(path: str) -> c_ast.FileAST:
    """
    Legge un file .c: preprocessa con gcc -E e parsa con pycparser.
    Richiede `gcc` nel PATH.

    Il preprocessore riceve sempre ``-DMNEMO`` così il sorgente può usare
    ``#ifdef MNEMO`` / ``#if defined(MNEMO)`` per rami specifici della toolchain Mnemo.
    """
    if not os.path.isfile(path):
        raise MnemoCompileError(f"file non trovato: {path}")
    if shutil.which("gcc") is None:
        raise MnemoCompileError(
            "serve `gcc` nel PATH per il preprocessore (-E). "
            "Installa build-essential (Debian/Ubuntu) o usa un ambiente con gcc."
        )
    # fake_libc_include (pycparser sorgente) non è sempre incluso nel wheel;
    # per file senza #include basta -E -std=c99. Con #include si può installare
    # pycparser da sorgente o aggiungere -I verso una copia degli header fake.
    # Mnemo modella tutti gli interi come word-size della VM. Fake headers in
    # `mnemo/fake_include/` definiscono size_t / int*_t / uint*_t / ptrdiff_t /
    # intptr_t come `int` o `unsigned int`. Path precede include di sistema via
    # `-I` prima del path system di gcc → priorità ai nostri header.
    cpp_args: list[str] = ["-E", "-std=c99", "-DMNEMO"]
    mnemo_fake = os.path.join(os.path.dirname(__file__), "fake_include")
    if os.path.isdir(mnemo_fake):
        cpp_args.insert(0, f"-I{mnemo_fake}")
        cpp_args.append("-nostdinc")
        # Auto-include stddef/stdint: size_t, int*_t, uint*_t disponibili
        # senza #include esplicito.
        cpp_args.extend([
            "-include", os.path.join(mnemo_fake, "stddef.h"),
            "-include", os.path.join(mnemo_fake, "stdint.h"),
        ])
    fake = _fake_libc_include()
    if os.path.isdir(fake):
        cpp_args.append(f"-I{fake}")
    try:
        text = preprocess_file(path, cpp_path="gcc", cpp_args=cpp_args)
        # `offsetof` (stddef.h di gcc) → `__builtin_offsetof(T, M)`. Pycparser
        # non lo parsa, quindi convertiamo in `__mn_offsetof_str("T","M")`,
        # gestito poi in c_lower.py come costante compile-time.
        if "__builtin_offsetof" in text:
            text = _rewrite_builtin_offsetof(text)
        parser = CParser()
        return parser.parse(text, path)
    except MnemoCompileError:
        raise
    except Exception as e:
        raise MnemoCompileError(f"parse C fallito: {e}") from e
