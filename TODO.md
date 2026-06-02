# TODO

## Bug aperti (verificati, fix rischioso/non banale)

- **Bitwise OR/AND/XOR perdono il bit 31 (segno).** `lib/bits.kairos`
  `__mn_and_into`/`__mn_or_into` iterano 31 bit (`until k==31`): il bit 31 non
  è mai impostato e manca la sign-extension. `-5|8` → 2147483643 invece di -5;
  `-1&-1` → 2147483647 invece di -1. Latente per AND/XOR quando l'operando con
  bit31 dà 0 nel risultato (passano -5^1, -5&8). Fix dipende dalla signedness
  (signed → sign-extend a -2^31; unsigned → +2^31 + mask u32) e bits.kairos è
  core per encrypt/des → riverificare round-trip + invertibility. Repro
  `c_test/bug_bitwise_or_sign.c`.
- **`char`/`unsigned char`: aritmetica non wrappa a 8 bit.** char aliasato a
  `int` → `unsigned char c=250; c+=10;` dà 260 invece di 4. Servirebbe mask
  0xFF sugli assegnamenti a var char; impatta string-ops → valutare. Repro
  `c_test/bug_uchar_wrap.c`.

## Migliorie / limiti noti (non bloccanti)

- **Indice array commutato `2[a]`** (== `a[2]`) non supportato: `array: la base
  dell'indicizzazione deve essere un nome` (probe `r17`). Sintassi rara.

- **Ricorsione mista self+mutua: possibile collisione di frame-key.** Il clone
  per la mutua usa `Frame.active` come depth, la self-rec usa il parsing `@N`
  del frame name (Janus.c). Una proc raggiunta SIA da self- SIA da mutua-
  ricorsione nello stesso path potrebbe generare chiavi `proc@depth`
  collidenti. Caso limite non coperto dai test (mutua a 2/3 vie + self pure
  OK). Verificare/serve uno schema di depth unificato se emerge.
- **`_Generic` non distingue `char` da `int`.** Mnemo aliasa `char` a `int`
  nel type-system → `_Generic((c), char:…, int:…)` sceglie sempre `int`.
  Probe `p22`. Richiede un tag di tipo `char` separato nel lowering.
- **Array di puntatori a funzione non supportati** (`int (*ops[2])(int)`).
  Probe `p07` → `array: elemento supportato solo se scalare/puntatore`.
  Solo fnptr scalari compile-time-resolved oggi.
- **Cruft debug VM**: blocco `#ifdef MNEMO_AGENT_LOG` in
  `kairos/src/vm/Janus.c` (END_PROC) scrive su path hardcoded
  `/home/nico/Desktop/mnemo/.cursor/debug-acb76d.log`. Morto salvo `-D`, ma da
  rimuovere.

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
