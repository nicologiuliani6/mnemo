# TODO

## OPEN

### [P3] opt-uncall self-recursion (fibonacci → fibonacci) — DEFERRED

Self-recursive callee con `--opt-uncall-user-calls`: forward CALL + uncall caller-side ok, ma inverse-walk profondo (inv>=15) su clone DELOCALato lascia `vars[24]` NULL → panic `XOREQ __mn_e<N> NULL frame=fibonacci@w<tid>_N`.

Guard `self_rec` re-installato in c_lower.py (`apply_uncall_opt`/`apply_void_uncall_opt` entrambi con `and not self_rec`). fib.c con `--opt-uncall-user-calls` torna 89 corretto.

Fix VM richiesto per rimuovere il guard:
- Capire perché fi=22 entra in pass inverse senza prima ri-eseguire LOCAL `__mn_e<N>`. Probabilmente `exec_branch_inverse` chiamato da UNCALL nesting opera su sub-range del body (skip proc-level LOCAL/DELOCAL).
- `tmp_alloc` INT slot mancanti per `fi != fi_reset` già implementato (vm_invert.h:1218-1226) ma non scatta per il caso.
- Considerare se opt-uncall pattern emit Mnemo è semanticamente compatibile con self-rec o servirebbe emit alternativo (es. inline manuale del callee body).

Tempo stimato: 6-10h + design review.

---

## C-subset features ancora da implementare

### Tipi / qualifiers

- Nessuna mancanza nota su int family. `char` come variabile, `short/long/long long`, `size_t`/`ptrdiff_t`/`intptr_t`/`uintN_t`, `enum` come tipo: tutti supportati.

### Puntatori

- Function pointer runtime: solo compile-time-resolved.

### Array

- Array element count > 1024 (`ARR_MAX`).

### Funzioni

- **Variadic user functions** (`int f(int n, ...)`). `<stdarg.h>` non implementato.

### Storage / linkage

- Nessuna mancanza nota su static/extern/register/auto in single-TU.

### Struct / union

- **Bit-fields runtime**: truncamento `unsigned x : N;` ora attivo
  per `f.x = E` con E costante a compile-time. Caso runtime
  (`f.x = v`) non trunca: `&` mask via bits.kairos è O(2^N) e
  blocca la VM. Workaround: const-folding esplicito lato C.
- **Flexible array members** (struct con `int a[];` finale).
- **Array come campo struct** (`struct Box { int data[4]; }`): le
  scritture `b.data[i] = X` non landano perché Mnemo alloca un
  singolo slot per il campo invece di N. Richiede modifica
  `_flatten_struct_fields` + `array_info` per i campi array.
- **Array di struct** (`struct P arr[10]`): non supportato (errore
  "array: elemento supportato solo se scalare").

### Stdlib

- **`<string.h>`** runtime (`strcpy`, `strncpy`, `memmove`, ...): non
  implementati. `strlen` / `strcmp` compile-time su literal/`char *p
  = "lit";`. `memcpy(dst, src, N)` / `memset(dst, v, N)` espansi
  a compile-time se dst (e src) sono array Mnemo e N costante.

### Control flow / misc

- **Direct self-recursion da main** (`int fib(int n){return fib(n-1)+fib(n-2);}` chiamata da main senza parallel2 wrap). Vedi opt-uncall self-rec sopra. Anche `gcd(a,b)` ricorsiva ritorna risultato sbagliato — recursion + return-inside-if non si compone bene.
- **`return` dentro `switch`/`if`**: la VM reversibile non ha early-exit. `case X: return V;` non propaga V al caller (return diventa no-op se non è l'ultima istruzione). Workaround: `int r; switch{...r=V; break;...} return r;`.
- **`continue` dentro `if` dentro `while`/`for`**: rompe IF/FI reversibile se l'if-then muta la guardia. Mnemo emette "[VM] IF/FI non reversibile".
- **Stato muta-guardia in loop** (state machines): `switch(state) { case 0: state=1; break; ...}` dentro while: la guardia non è più vera all'uscita del case.
- **`_Generic`** (C11). Compile-time, fattibile via AST pre-pass.

### Semantica reversibile

- **Memory aliasing arbitrario**: caller-callee aliasing tra mem cells non sempre supportato.
- **Side effects con risultato non-restored**: `x = f(x)` dove `f` ha side-effect richiede uncall implicit (non ancora wired).

### printf

- **printf `%s` con argomento runtime** (non letterale né `char *x = "lit"`): non supportato. Le stringhe come parametri funzione/variabili dinamiche non hanno binding al payload bytes nella VM.
- **printf `%u` runtime su valori negativi**: stampa la rappresentazione signed (no reinterpretazione 2-complement → `2^32 + val`). Su `unsigned` non-negativi funziona.
- **printf width runtime** (`%5d`, `%-5d`, `%05d` con argomento variabile): ignorati silenziosamente. Richiede contare cifre del valore runtime (helper Kairos con divmod chain). Flag `+`/` ` runtime su `%d` ora supportati via `__mn_putd_plus` / `__mn_putd_space`.

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
