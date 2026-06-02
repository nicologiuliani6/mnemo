# TODO

Nessun lavoro aperto. Sotto: note sui lavori chiusi e i limiti
intenzionali (bounded-by-design, non bug).

## Bounded-by-design (non bug)

- **`STACK_MAX=4096`** (`stack.h`, lo `Stack` di `Var*` usato da
  `LocalVariables`): profondità di `local` per-Frame. Irraggiungibile via Mnemo
  (il layout cap­pa le celle a 2048 < 4096). Convertirlo a dinamico romperebbe la
  copia by-value dello `Stack` (inline) usata nel save/restore di
  CALL/UNCALL/par/inversione (~10 siti + `CallRecord.saved_local_vars`) → rischio
  alto sul core fragile per zero guadagno raggiungibile. Si tiene statico. NB: la
  crescita dinamica di `Frame.vars` (oltre 4096) È verificata di per sé — un
  `.kairos` scritto a mano con 5000 `local` somma corretto una volta alzato
  `STACK_MAX`; è solo lo `Stack` a fare da tappo prima.
- **`IF_BRANCH_STACK_MAX=65536`** (thread-local, `vm_ops.h`): stack di profondità
  IF per thread. 65536 IF annidati in un singolo path di esecuzione è
  irraggiungibile; la versione thread-local dinamica leakerebbe a thread-exit →
  si tiene statico, stesso criterio dei `DBG_MAX_*`.
- **`DBG_MAX_BREAKPOINTS=256`, `DBG_MAX_HISTORY=4096`**: limiti del debugger DAP
  (history = ring-buffer). Solo debug interattivo.

## Note su lavori chiusi

**VM Kairos: dyn alloc per-Frame — FATTO**: i campi per-Frame erano array
statici (`vars[MAX_VARS]`, `label[MAX_LABEL]`, `param_indices[MAX_PROC_PARAMS]`,
`trace_window_stack[VM_TRACE_WIN_STACK_MAX]`) → ora heap che cresce on-demand via
`frame_ensure_vars/labels/params/trace` (init cap = vecchio MAX, quindi fast path
identico per i programmi noti; la crescita è valvola di sicurezza, niente più
hard cap per-Frame). Rimossi i campi morti `loop_restart_i/loop_bottom_i/
loop_counter` + macro `MAX_NESTED`. La struct `Frame` non ha più cap statici.
Commit Kairos `feat(vm): Frame.vars dinamico` + `feat(vm): Frame label/
param_indices/trace dinamici`. Verificato 25/25 unit, 168/168 gcc-compat, 36/36
c_examples, encrypt `--check-invertibility`, fib/parallel2_fib (clone+par).

**Pointer pool runtime growable — FATTO** (heap VM dinamico `vm->mn_pool`):
`malloc` in loop a bound runtime senza free ora cresce on-demand, niente
`--ptr-pool-size`. Modello ibrido: slot < heap_base = memoria nominata
(`__mn_mem*`, dispatch `if slot==k`, bancato se > ~998 celle); slot >= heap_base
= heap senza alias → procedure `__mn_pool_*_dyn` su `vm->mn_pool` via ops VM
reversibili POOLPUSH/POOLADD/POOLGET (vedi commit Kairos `feat(vm): heap
puntatori dinamico`). Verificato forward + `--check-invertibility` (malloc
base/concorrente/loop/runtime, banked+dynamic), encrypt round-trip intatto,
168/168 gcc-compat. Regression `tests/test_pool_runtime_loop.py` +
`tests/test_ptr_pool_emit.py`. NB: il dispatch statico bancato (> 998 celle
*nominate* accedute via puntatore) resta lento nell'interprete (O(N) per accesso)
ed è un limite pre-esistente ortogonale, non legato all'heap.

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
