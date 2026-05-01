"""Parsing C con pycparser + preprocessore (gcc -E)."""

from __future__ import annotations

import os
import shutil

from pycparser import c_ast, parse_file

from mnemo.errors import MnemoCompileError


def _fake_libc_include() -> str:
    import pycparser as _p

    return os.path.join(os.path.dirname(_p.__file__), "utils", "fake_libc_include")


def parse_c(path: str) -> c_ast.FileAST:
    """
    Legge un file .c: preprocessa con gcc -E e parsa con pycparser.
    Richiede `gcc` nel PATH.
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
    cpp_args = ["-E", "-std=c99"]
    fake = _fake_libc_include()
    if os.path.isdir(fake):
        cpp_args.append(f"-I{fake}")
    try:
        return parse_file(
            path,
            use_cpp=True,
            cpp_path="gcc",
            cpp_args=cpp_args,
        )
    except Exception as e:
        raise MnemoCompileError(f"parse C fallito: {e}") from e
