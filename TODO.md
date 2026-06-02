# TODO

## Lavori grossi futuri (aperti)

Entrambi gli item richiedono lo stesso pezzo mancante: un **modello di memoria
VM dinamico** (heap reversibile con accesso indicizzato O(1) + crescita
on-demand). Sono gli unici lavori non completati; tutto il resto (auto-sizing
pool, modello header, pool bancato, malloc+free in loop, loop a bound costante,
diagnostica bound-runtime, dump forward sotto `--check-invertibility`, bump
statici dei Frame fields) è già fatto e coperto da regression.

### 1. VM Kairos: dyn alloc per-Frame (non-urgente)

I Frame fields (`MAX_VARS=4096`, `MAX_NESTED=4096`, `MAX_PROC_PARAMS=1024`,
`MAX_LABEL=16384`, `VM_TRACE_WIN_STACK_MAX=4096`, `IF_BRANCH_STACK_MAX=65536`)
sono **bump statici** ampi, non array dinamici. Future-proofing: sostituire il
bump con `realloc` inline per-Frame (come già fatto per `vm->frames`,
`branch_trace`, `mn_hist_floor_snaps`, `CallRecord`). Non urgente: i valori
correnti coprono tutti i casi noti. `kairos_limits.py` lato Mnemo già allineato
(`KAIROS_MAX_PROC_PARAMS=1000 ≤ 1024`).

Intenzionalmente bounded (non bug): `DBG_MAX_BREAKPOINTS=256`,
`DBG_MAX_HISTORY=4096` sono limiti del debugger DAP (history = ring-buffer).

### 2. Mnemo: pointer pool runtime growable

`malloc` in loop a bound **runtime** senza `free` (allocazioni accumulate, N non
noto a compile-time) richiede `--ptr-pool-size N` esplicito. Oggi il caso è
**diagnosticato** a compile-time (errore chiaro invece di miscompile), ma il fix
VERO — pool che cresce a runtime senza flag — manca: il pool è un array di celle
`__mn_mem*` con dispatch `if slot==k` generato a compile-time → NON cresce a
runtime. Servirebbe una primitiva VM `pool_grow N` reversibile + accesso
indicizzato O(1) a un heap dinamico. Dipende da [[1. VM Kairos: dyn alloc]].
Nota: con `free` nel corpo i blocchi si riusano (LIFO) e il pool resta piccolo,
quindi il solo caso problematico è malloc-in-loop-runtime SENZA free.

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
