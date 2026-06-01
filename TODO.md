# TODO

## Note / feature

### `--check-invertibility` + `--vm-dump`: dump dello stato forward (DONE)

Prima il VM dump usciva vuoto (o non usciva affatto) con
`--check-invertibility`: il wrapper `main` fa `call __main__ ; uncall
__main__`, l'uncall reverte tutto e il `vm_dump` finale (post-uncall)
trova memoria azzerata; se l'uncall fallisce (es. `kernel` con
ssend/channel → `[VM] SSEND: destinazione non è channel!`) la VM esce 1
prima del dump.

Fix: nuovo builtin Kairos `dump()` → opcode `DUMP` (`vm_dump_active`,
dump del frame attivo via `get_findex`). Mnemo lo inietta in coda a
`__main__` (blocco `__mn_inv_dump`), PRIMA dei delocal e dell'uncall →
stato forward sempre stampato. `DUMP` è no-op nell'inverso (`INVOP_DUMP`)
e soppresso durante replay (`suppress_show`). Flag `vm->mn_dumped` salta
il dump finale post-uncall (evita doppio header).

**Caveat native-arith nell'inversione**: con native-arith ON (Janus.c
UNCALL path `mn_native_arith_uncall_inverse`), `--check-invertibility`
verifica l'inverso C nativo O(1) di mul/divmod/bits, NON la reversibilità
del codice Kairos di `mul.kairos`/`divmod.kairos`/`bits.kairos`. Per
stressare il lib-code reversibile vero → check-invertibility SENZA
native-arith.

## Lavori grossi futuri

### 1. VM Kairos: allocazione dinamica strutture interne (parziale)

**Già dinamici**:
- `vm->frames` (era `[MAX_FRAMES=200]`) → heap, cresce on-demand
  via `vm_ensure_frame_cap` (init=256, raddoppia).
- `CallRecord *cs` in vm_run_BT cresce dinamicamente.
- `vm->branch_trace` (era `[VM_BRANCH_TRACE_MAX=131072]`) → heap,
  raddoppia in op_jmpf.
- `IF_BRANCH_STACK_MAX` bumped 256→65536 (thread-local stack).
- `vm->mn_hist_floor_snaps` (era `[MNEMO_HIST_SNAP_DEPTH=384]`) → heap,
  raddoppia in CALL __mn_hist_floor_snap (commit 2026-05-31).
- `Var.value` (TYPE_STACK) e `Channel.buf`: `VAR_STACK_MAX_SIZE=512` e
  `VAR_CHANNEL_MAX_SIZE=128` sono solo alloc INIZIALE; tutti i push
  fanno `realloc(stack_len+1)` per-elemento (no hard cap, però perf
  subottimale: refactor a doubling amortizzato è auspicabile).
- **`vm->frames` ora `Frame **`** (commit Kairos 3036648, 2026-05-31):
  Frame allocati individualmente sull'heap → realloc del pointer array
  non sposta Frame. Sblocca bump safe di MAX_NESTED/MAX_VARS senza
  rompere ex33 parallel2_fib.
- **Cap dell'inverse per disj-chain runtime-index** (commit Kairos
  58017d1): `collect_ifs` stack `[64]`, `exec_branch_inverse` `lp/ln[512]`,
  `invert_op_to_line` `MAX_LINES=1024`, `MAX_IFS=256` (_fa_cache.ifs +
  exec_branch) → tutti heap, dimensionati a frame/branch span. Risolve il
  vecchio limite «store `g[i]` a indice runtime su array > 64 elementi
  fallisce/SIGSEGV sotto --check-invertibility»: ora inverte fino ad
  ARR_MAX=1024 (verificato N=300/400 single-store; array[100] in loop
  deterministico). Regression guard `c_test/inv_bigidx.c`. NB: la versione
  con loop su tutti gli N elementi è O(N²) nell'interprete → lenta (non un
  bug) per N grandi.

**Frame fields statici — bumpati (FATTO)**: valori correnti in
`vm_types.h` già oltre i vecchi target: `MAX_VARS=4096`, `MAX_LABEL=16384`,
`MAX_NESTED=4096`, `MAX_PROC_PARAMS=1024`, `VM_TRACE_WIN_STACK_MAX=4096`,
`IF_BRANCH_STACK_MAX=65536`. `kairos_limits.py` allineato
(`KAIROS_MAX_PROC_PARAMS=1000 ≤ 1024`). Resta come future-proof la dyn
alloc per-Frame (realloc inline) al posto del bump statico, ma non urgente.

**Intenzionalmente bounded (non bug)**: `DBG_MAX_BREAKPOINTS=256`,
`DBG_MAX_HISTORY=4096` sono limiti del debugger DAP (solo debug). La
history è già un ring-buffer (shift a MAX in `vm_debug.h`), i breakpoint
256 sono ampi per uso interattivo → nessuna azione necessaria.

Update `kairos_limits.py` lato Mnemo per allinearsi a quanto cambia.

### 2. Mnemo: pointer pool runtime growable (auto-sizing già fatto)

**Già fatto**: pool size auto-inferito da `_infer_ptr_pool_size`. Ora
dimensiona dalla SIZE di ogni `malloc`/`calloc` (non più dal solo numero di
call-site): `malloc(sizeof(int)*N)` → N celle (commit Mnemo b986723,
regression `generic_malloc_block.c`). Banked pools sopra
`MONOLITHIC_POOL_MEM_MAX`.

**RISOLTO — `malloc`+`free` dentro un loop perdeva iterazioni** (commit
Mnemo): `__mn_pool_free` generato faceva `push(ctr, __mn_hist); ctr -= 1`
per il dec-ctr LIFO, ma `op_push` AZZERA la sorgente → `ctr` diventava
`0-1 = -1` invece di `ctr-1`. Single malloc/free non lo notava (programma
finiva); in un loop il contatore corrotto faceva drift­are gli slot
(`for(i=0;i<3;i++){…malloc;*p=i;print;free;}` → `0 0 2`). Fix:
`ptr_pool_kairos.py` emette `ctr -= 1` SENZA push (già reversibile,
inverse = `ctr += 1`; la guardia `ctr0==need` non tocca ctr). Lo stesso
errore era nel pool bancato. Regression `generic_malloc_loop_free.c`.
Verificato forward + `--check-invertibility`.

**RISOLTO (pool monolitico) — malloc concorrenti multi-cella** (commit
Mnemo): adottato il **modello header** (opzione 2). Ogni malloc di N celle
occupa N+1 celle a partire da `ctr`: `mem{ctr}=N` (header, scritto dal
lowering via `__mn_pool_store`), dati in `mem{ctr+1..ctr+N}`, puntatore
utente = `ctr+1`, `ctr += N+1`. `free(p)` rilegge N da `mem{p-1}` (via
`__mn_pool_load`) e decrementa `ctr` di N+1 se il blocco è l'ultimo
allocato (riuso LIFO). `alloc`/`free` toccano solo `ctr` (mem-free); lo
store auto-resetta l'header al riuso (push). Verificato: 2 e 3 malloc
concorrenti, sequenziali, loop+free, single, + `--check-invertibility`;
167/167 gcc-compat (regression `generic_malloc_concurrent.c`). Sizing pool
= Σ(nblk+1)+sentinella (`_infer_ptr_pool_size`).

**RISOLTO — pool BANCATO (> ~998 celle)** (commit Mnemo): il modello header
ora funziona anche col pool bancato. Due bug:
1. il dispatch slot→(banca,offset) usa `__mn_divmod_nonneg`, ma la lib divmod
   era auto-inclusa solo se il C usa `/`/`%` → proc chiamata ma non definita →
   SEGV in `get_findex`. Fix: includi `divmod`(+`mul`+`helpers`) quando il pool
   è bancato.
2. l'header store passava `__mn_pool_ctr` diretto al divmod del dispatch, che
   CONSUMA il dividendo → ctr azzerato → alloc vedeva ctr=0 → slot drift. Fix:
   passa una COPIA di ctr allo store dell'header.
Regression `tests/test_pool_banked_malloc.py` (concorrente + check-invertibility
con --ptr-pool-size 1500).

**RISOLTO (loop a bound costante)** (commit Mnemo): `malloc` dentro un loop
`for`/`while` con trip-count COSTANTE (riconosciuto da `_const_loop_trip_count`:
`for(i=A; i</<=/>/>=B; i++/--/+=/-=K)` con A,B,K costanti) è ora auto-sizato ×
trip-count, quindi malloc-in-loop senza free (blocchi accumulati) funziona
senza `--ptr-pool-size`. Regression `generic_malloc_loop_nofree.c`.

**Open (feature) — solo bound RUNTIME**: `malloc` in loop con N iterazioni
*runtime* (non costante, no free) resta non inferibile staticamente → richiede
`--ptr-pool-size N_max`. Il fix vero (crescita on-demand) richiede un modello
di memoria VM dinamico: il pool attuale è un array di celle `__mn_mem*` con
dispatch `if slot==k` generato a compile-time → NON cresce a runtime. Servirebbe
una primitiva VM `pool_grow N` reversibile + accesso indicizzato O(1) a un heap
dinamico (nuovo modello di memoria). Lavoro grosso, dipende da
[[1. VM Kairos: allocazione dinamica strutture interne]]. Nota: con `free` in
loop il blocco si riusa (LIFO) e il pool resta piccolo, quindi il caso davvero
problematico è malloc-in-loop-runtime SENZA free (allocazioni accumulate).

---

## Non fattibile per modello reversibile / VM Kairos

Features escluse strutturalmente — non saranno implementate finché Mnemo target una VM reversibile a interi.

### Rompono reversibilità

- **`goto`** — controllo di flusso non-strutturato, no inverse walk.
- **`setjmp` / `longjmp`** — stack unwinding non reversibile.
- **`exit(n)` fuori da main** — terminazione non reversibile dalla profondità di stack arbitraria. (`exit(n)` DENTRO main è supportato via AST rewrite a `return n`.)
- **`abort()` fuori da main** — terminazione asincrona non reversibile. (Dentro main supportato come `return 134`.)
- **`signal` / signal handlers** — interruzioni asincrone.
- **Inline asm** (`__asm__`, `asm volatile`) — no IR.

### Niente floating-point

VM Kairos opera solo su interi. Esclusi:

- **`float`, `double`, `long double`**.
- **`_Complex`** (C99 complex).
- **`<math.h>`** (sin, cos, sqrt, …).

### Niente I/O reale / syscalls

VM non ha syscalls oltre `printf`/`putchar`/`puts` (output testuale gestita dal frontend Python).

- **`scanf`, `getchar`, `fgets`** — niente input.
- **`fopen`, `fprintf`, `fclose`, `fread`/`fwrite`** — niente filesystem. (`fflush`/`feof`/`ferror`/`clearerr`/`setvbuf`/`fileno` ritornano 0 via AST rewrite per compatibilità sintattica.)
- **`<time.h>`** — niente clock/timer reali. (`time()`/`clock()` ritornano 0 via AST rewrite per compatibilità sintattica.)
- **`<unistd.h>`, `<sys/*>`** — niente syscalls POSIX.
- **`<stdlib.h>` `system`** — exec di processo esterno. Solo `malloc`/`free` via ptr_pool. (atoi e getenv supportati: atoi compile-time, getenv ritorna NULL.)
- **`calloc`, `realloc`** — semantica re-alloc difficile da invertire.
- **`errno` set/mutate** — global mutabile non-modellata. Solo *lettura* di errno supportata: `<errno.h>` fake_include espone `errno` come int 0 (no syscall ⇒ nessun errore mai). Costanti E* definite.
- **`argv` POSIX reali** — stringhe da OS non disponibili (stub sintattico).

### Concorrenza non-π

VM usa solo channel π-calcolo come primitiva di sync. Esclusi:

- **`_Atomic`** — semantica memory-order LL/SC non modellata.
- **`pthread_*`** generale — solo `pthread_parallel2` e `pthread_mutex_*` (lowered a par/channel).

### Multi-TU / linker

Mnemo è single-file compiler. Esclusi:

- **Translation unit multipli** (`gcc a.c b.c -o`).
- **`extern` cross-TU** (linker globale assente).
- **`#include` di header utente con definizioni** — `gcc -E -DMNEMO` espande tutto in un blob, ma typedef/struct cross-file possono confondere il layout.

### GCC-specific

- **`__attribute__((…))`** — packed, aligned, used, weak, etc.
- **`__builtin_*`** — `__builtin_expect`, `__builtin_unreachable`, etc.
- **Nested function definitions** (estensione GCC).

### VLAs

- **`int a[n]` con `n` runtime** — layout cells deve essere compile-time per partition PAR e ptr-pool.
