"""
Parole riservate del lexer Kairos (src/frontend/lexer.py `reserved`).
Gli identifier C che coincidono vanno rinominati in emissione `.kairos`, altrimenti
(`procedure loop`, ecc.) il frontend Kairos fallisce con «token non atteso».
"""

from __future__ import annotations

# Allineato a kairos/src/frontend/lexer.py chiavi dict `reserved`
KAIROS_RESERVED_IDS: frozenset[str] = frozenset(
    (
        "procedure",
        "int",
        "stack",
        "nil",
        "channel",
        "empty",
        "local",
        "delocal",
        "call",
        "uncall",
        "if",
        "then",
        "else",
        "fi",
        "from",
        "do",
        "loop",
        "until",
        "par",
        "and",
        "rap",
    )
)


def kairos_escape_id(identifier: str) -> str:
    """Nome Kairos sicuro da usare dove serve un ``ID`` (procedure, ``call``, ``uncall``)."""
    if identifier in KAIROS_RESERVED_IDS:
        return f"__mn_k_{identifier}"
    return identifier
