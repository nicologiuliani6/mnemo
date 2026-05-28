"""
Limiti empirici della VM Kairos (kairosapp): procedura con >100 parametri → PARAM già definito;
chiamata con troppi argomenti → exit -7 / errore.

Il pool `__mn_pool_*` e le chiamate utente passano `__mn_mem0..N-1`: quando N supera questi
soglia serve «banking» (procedure per slice) o inlining.
"""

from __future__ import annotations

# VM Kairos: `Frame.param_indices[MAX_PROC_PARAMS]` + `CallRecord.saved_params[MAX_PROC_PARAMS]`
# definito in src/vm/vm_types.h come 1024. Mnemo usa una soglia leggermente inferiore.
KAIROS_MAX_CALL_ARGS = 1000

# Procedure `procedure p(...)`: stessa frontiera del CALL.
KAIROS_MAX_PROC_PARAMS = 1000

# `__mn_pool_store(slot, val, __mn_mem0..)` ha 2+N argomenti nella call IR.
MONOLITHIC_POOL_MEM_MAX = KAIROS_MAX_CALL_ARGS - 2

# Slice per procedure bancate (2 + BANK <= KAIROS_MAX_CALL_ARGS).
# Massimo celle per banca: `call` deve restare ≤ KAIROS_MAX_CALL_ARGS (2 + BANK).
POOL_BANK_SIZE = MONOLITHIC_POOL_MEM_MAX

# Limite compile-time su `--ptr-pool-size` / celle layout (allineato al lowering).
PTR_POOL_MAX = 2048
