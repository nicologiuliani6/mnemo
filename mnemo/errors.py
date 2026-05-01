"""Errori Mnemo."""


class MnemoError(Exception):
    """Base."""


class MnemoCompileError(MnemoError):
    """Errore di compilazione C → Kairos."""
