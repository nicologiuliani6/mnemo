# TODO

## Librerie implementabili in Mnemo (compatibili modello reversibile)

Stdlib C subset realizzabile dato che già abbiamo `malloc`/`free`,
`printf`/`putchar`/`puts`, `memcpy`/`memset`/`strcpy`/`strncpy`/`memmove`
compile-time, `strlen`/`strcmp` compile-time, variadic via `__mn_va_arg`,
ptr_pool, IF/loop/struct/union, reversibili int64 cell.

### stdlib.h

- **`abs(int)` / `labs(long)` / `llabs(long long)`** — `if (x < 0) -x else x`. Reversibile diretto.
- **`div_t div(int, int)` / `ldiv` / `lldiv`** — struct con quoziente e resto. Wrapper su `__mn_divmod_signed`.
- **`abort()`** — Mnemo emit `show("abort\n")` + halt (no reverse needed, halt è fine).
- **`atoi(const char *)`** — compile-time su letterale (analogo `strlen` compile-time esistente).

### string.h aggiuntivi

- **`strcat(dst, src)` / `strncat(dst, src, N)`** — compile-time se dst array Mnemo, src letterale o char[]. Append byte-per-byte.
- **`strchr(s, c)` / `strrchr(s, c)`** — compile-time su letterale: ritorna indice/NULL.
- **`strstr(haystack, needle)`** — compile-time su letterali entrambi. Naive search.
- **`memcmp(a, b, N)`** — compile-time se entrambi array Mnemo + N const. Confronto byte-wise.
- **`strspn` / `strcspn` / `strpbrk`** — char-class compile-time su letterali.
- **`strdup`** — alloca via ptr_pool + memcpy compile-time. Solo se src letterale.

### ctype.h

- Già implementato come macro inline in `mnemo/fake_include/ctype.h`. Funziona runtime per ogni char.

### math.h subset integer

- **`min(a, b)` / `max(a, b)`** — non standard ma utile. `if a<b then b else a`. Reversibile.
- **Power-of-2 utilities**: `is_pow2(x) = (x & (x-1)) == 0` compile-time se x const.

### Custom Mnemo helpers

- **`itoa(int n, char *buf, int base)`** — base 10/16/8/2. Buf array Mnemo. Itera divmod_fast.
- **`snprintf(buf, N, fmt, ...)`** — compile-time fmt parsing (analogo a printf). Scrive in buf array.
- **`memswap(a, b, N)`** — scambio byte-wise reversibile. Utile per puzzles reversibili.

### Concorrenza extra (π-channel based)

- **`mnemo_kairos_broadcast(channel, value)`** — multi-recv pattern via fanout di srecv.
- **`mnemo_barrier_2(b)`** — sync 2 worker via channel pair (già pattern in `lib/mps.h`).

### Reversibility utilities

- **`mnemo_snapshot(cells*, N)` / `mnemo_restore(cells*, N)`** — XOR snapshot esplicito di N celle in slot dedicato. Helper per opt-uncall manuale.
- **`mnemo_assert_reversible(expr)`** — wrappa expr in IF/FI per verificare proprietà inversa a runtime.

---

## Non fattibile per modello reversibile / VM Kairos

Features escluse strutturalmente — non saranno implementate finché Mnemo target una VM reversibile a interi.

### Rompono reversibilità

- **`goto`** — controllo di flusso non-strutturato, no inverse walk.
- **`setjmp` / `longjmp`** — stack unwinding non reversibile.
- **`exit(n)`** dentro funzioni — terminazione non reversibile (la VM gestisce solo return da main).
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
- **`fopen`, `fprintf`, `fclose`, `fread`/`fwrite`** — niente filesystem.
- **`<time.h>`** — niente clock/timer.
- **`<unistd.h>`, `<sys/*>`** — niente syscalls POSIX.
- **`<stdlib.h>` non-mem**: `atoi`, `getenv`, `system`. Solo `malloc`/`free` via ptr_pool.
- **`calloc`, `realloc`** — semantica re-alloc difficile da invertire.
- **`errno`** — global mutabile non-modellata.
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
