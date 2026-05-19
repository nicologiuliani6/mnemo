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
    # Mnemo modella tutti gli interi come word-size della VM. Aliasing dei tipi
    # stdlib (intN_t, uintN_t) a int/unsigned via -D: utili anche senza include.
    # size_t/ssize_t/ptrdiff_t/intptr_t/uintptr_t NON ridefinite via -D perché
    # entrano in conflitto con typedef di stddef.h se l'utente include header
    # standard. Il sorgente che li usa deve includere <stddef.h>/<stdint.h>;
    # i typedef risultanti (es. `unsigned long`) sono già accettati come scalari.
    cpp_args = [
        "-E", "-std=c99", "-DMNEMO",
        "-Dint8_t=int", "-Dint16_t=int", "-Dint32_t=int", "-Dint64_t=int",
        "-Duint8_t=unsigned int", "-Duint16_t=unsigned int",
        "-Duint32_t=unsigned int", "-Duint64_t=unsigned int",
    ]
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
