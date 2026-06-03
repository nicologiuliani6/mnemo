# TODO

## Bug aperti (verificati, fix rischioso/non banale)

- **Confronti unsigned vs valore non-zero con high-bit** (es. `u1 < u2` con
  u1≥2^31): non coperti (Mnemo confronto signed). Il caso comune `unsigned <,>= 0`
  e l'aritmetica char/unsigned-char (wrap 8 bit) sono ORA gestiti.

## Ottimizzazioni mancanti

- **opt-uncall su funzioni pool che scrivono attraverso un ptr-param**:
  ancora escluse. La maggior parte delle funzioni pool-using (malloc-loop con
  return/globale) è ORA ottimizzata (`cells_max -50%` su poolopt, encrypt/des
  invertibili intatti). Restano escluse SOLO quelle che fanno `*out=…`/`out[i]=…`
  su un puntatore-parametro (`pool_uncall_blocked = pool ∩ writes-ptr-param`):
  l'uncall inverte una scrittura su una cella del frame chiamante non coperta
  dallo snap/swap → divergenza (repro `c_test/bug_malloc_in_function.c` sotto
  `--opt-uncall`). Per coprirle servirebbe estendere lo snapshot opt-uncall alle
  celle scritte via ptr-param fuori dal touch-set — lavoro fine.

## Migliorie / limiti noti (non bloccanti)

- **Campo union/struct annidato `u.s.a`** non supportato: `union: un solo
  livello di campo` (probe `v03`).
- **`char *n; n = "literal";` (riassegnazione da letterale) + `printf("%s",n)`**
  non supportato in alcuni contesti (es. dentro `switch`): `letterale stringa
  non è un valore intero` (probe `v12`). L'init diretto `char *p="..."` invece
  funziona.
- **`_Generic` non distingue `char` da `int`.** Mnemo aliasa `char` a `int`
  nel type-system → `_Generic((c), char:…, int:…)` sceglie sempre `int`.
  Probe `p22`. Richiede un tag di tipo `char` separato nel lowering.
- **Array di fn-ptr a indice RUNTIME** (`ops[i](…)` con i variabile): solo
  l'indice COSTANTE è risolto a compile-time. Il runtime servirebbe una
  dispatch-chain sui candidati. Sintassi rara.

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
