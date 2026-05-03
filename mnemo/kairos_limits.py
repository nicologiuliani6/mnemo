"""
Limiti empirici della VM Kairos (kairosapp): procedura con >100 parametri → PARAM già definito;
chiamata con troppi argomenti → exit -7 / errore.

Il pool `__mn_pool_*` e le chiamate utente passano `__mn_mem0..N-1`: quando N supera questi
soglia serve «banking» (procedure per slice) o inlining.
"""

from __future__ import annotations

# Chiamata `call p(a0,...,ak)` stabile fino a ~65 argomenti nel tester locale.
KAIROS_MAX_CALL_ARGS = 64

# Procedure `procedure p(...)` stabili fino a 100 parametri int.
KAIROS_MAX_PROC_PARAMS = 100

# `__mn_pool_store(slot, val, __mn_mem0..)` ha 2+N argomenti nella call IR.
MONOLITHIC_POOL_MEM_MAX = KAIROS_MAX_CALL_ARGS - 2

# Slice per procedure bancate (2 + BANK <= KAIROS_MAX_CALL_ARGS).
# Massimo celle per banca: `call` deve restare ≤ KAIROS_MAX_CALL_ARGS (2 + BANK).
POOL_BANK_SIZE = MONOLITHIC_POOL_MEM_MAX

# Limite compile-time su `--ptr-pool-size` / celle layout (allineato al lowering).
PTR_POOL_MAX = 2048
