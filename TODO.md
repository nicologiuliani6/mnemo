# TODO

## OPEN

### [P3] opt-uncall self-recursion (fibonacci → fibonacci) — DEFERRED

Self-recursive callee con `--opt-uncall-user-calls`: rimuovendo il guard `self_rec`,
fib.c crasha durante uncall ricorsivo con `POP: stack vuoto! frame=fibonacci@<...>
dest=__mn_eN stack=__mn_scratch inv=N`. Il primo pop nell'inversione del corpo
ricorsivo trova `__mn_scratch` vuoto, anche se forward ha pushato N elementi.

Guard `self_rec` resta installato in c_lower.py (`apply_uncall_opt`/
`apply_void_uncall_opt` entrambi con `and not self_rec`). fib.c con
`--opt-uncall-user-calls` torna 89 corretto.

Stato delle indagini precedenti:
- **FIXED nel VM (commit kairos `fix(vm): make collect_ifs/collect_loops scan
  non-mutating + restore '\n' before recursive scans`)**: race condition su
  `*nl='\0'`/`*nl='\n'` nel buffer condiviso. `collect_ifs` veniva chiamata
  ricorsivamente da CALL/UNCALL con un `'\0'` ancora attivo sul buffer del loop
  esterno → `strchr` early-exit → `fi_label_line=0` → inversione del ramo ELSE
  saltava → XOREQ su locals non riallocati. Adesso scansioni non-mutanti +
  restore '\n' prima di recursive scan.
- **Root cause del secondo bug**: il VM in `invert_op_to_line` JMPF_ELSE handler
  (vm_invert.h:1075-1124) usa `vm->frames[fi_reset].recursion_depth` per
  "replay" l'inversione del ramo ELSE N volte (depth=N) + THEN una volta. È il
  meccanismo che permette di invertire un singolo `uncall fibonacci` ricorsivo
  al top livello: la VM rigioca tutti i livelli interni.
  Ma con `--opt-uncall-user-calls` self-rec si emette `call helper(...) +
  snap + uncall helper(...)` ANCHE INTERNAMENTE in helper body. L'uncall
  interno aspettava di invertire UNA SOLA chiamata (quella appena fatta), ma
  la VM lo tratta come uncall "outer" e replay ELSE N volte → pop su scratch
  più volte di quanto pushato → `POP stack vuoto`. **Incompatibilità di design
  fra opt-uncall pattern emit e recursion_depth replay del VM**.

Fix VM/lower richiesto per rimuovere il guard:
- **Strada A (VM)**: distinguere "outer uncall" (da chiamante non-helper) da
  "inner opt-uncall uncall" (da helper su sé stesso). L'inner deve invertire
  un solo livello, l'outer N livelli. Possibile flag su frame
  `recursion_depth_at_call` da snapshot e confronto.
- **Strada B (Mnemo)**: per self-rec, non emettere il pattern call+uncall ma
  un'inversione manuale (XOR delle celle toccate + scratch push). Più simile
  al non-opt path.
- **Strada C**: vietare opt-uncall su self-rec (status attuale).

Tempo stimato: 6-10h + design review.

---

## C-subset features ancora da implementare

### Tipi / qualifiers

- Nessuna mancanza nota su int family. `char` come variabile, `short/long/long long`, `size_t`/`ptrdiff_t`/`intptr_t`/`uintN_t`, `enum` come tipo: tutti supportati.

### Puntatori

- Function pointer runtime: solo compile-time-resolved.

### Funzioni

- **Variadic user functions** (`int f(int n, ...)`). `<stdarg.h>` non implementato.

### Storage / linkage

- Nessuna mancanza nota su static/extern/register/auto in single-TU.

### Struct / union

- **Flexible array members** (struct con `int a[];` finale).

### Stdlib

- **`<string.h>`** runtime: `strlen` / `strcmp` compile-time su literal/`char *p
  = "lit";`. `memcpy(dst, src, N)` / `memset(dst, v, N)` espansi a compile-time
  se dst (e src) sono array Mnemo e N costante. Ora anche `strcpy(dst, src)`,
  `strncpy(dst, src, N)` e `memmove(dst, src, N)` compile-time-expanded con dst
  array Mnemo (src letterale o char[]). Caso completamente runtime (dst dinamico,
  N runtime) richiede loop variable-length non rappresentabile reversibilmente
  con bound staticamente noto.

### Control flow / misc

- **Direct self-recursion da main** (`int fib(int n){return fib(n-1)+fib(n-2);}` chiamata da main senza parallel2 wrap). Vedi opt-uncall self-rec sopra.
- **`return` dentro `if`/`switch`**: pre-pass `_transform_switch_returns`, `_transform_if_chain_returns`, `_transform_early_return_if_then_return` e `_transform_general_early_returns` gestiscono switch-only, if/else-chain-only, body con `if(c) return E;` come primo stmt + return finale, e ora qualsiasi numero di stmt prima/dopo `if(c) return E;` (cascade ricorsivo, cond snapshot in `__mn_g_k` per stabilità fi). Resta TODO: return in loop body (richiede return-flag globale).
- **`continue` dentro `if` dentro `while`/`for`**: rompe IF/FI reversibile se l'if-then muta la guardia. Mnemo emette "[VM] IF/FI non reversibile".
- **Stato muta-guardia in loop** (state machines): `switch(state) { case 0: state=1; break; ...}` dentro while: la guardia non è più vera all'uscita del case.

### Semantica reversibile

- **Memory aliasing arbitrario**: caller-callee aliasing tra mem cells non sempre supportato.
- **Side effects con risultato non-restored**: `x = f(x)` dove `f` ha side-effect richiede uncall implicit (non ancora wired).

### printf

- **printf `%s` con argomento runtime** (non letterale né `char *x = "lit"`): non supportato. Le stringhe come parametri funzione/variabili dinamiche non hanno binding al payload bytes nella VM.
- **printf `%u` runtime su valori negativi**: stampa la rappresentazione signed (non `2^32 + val`). Richiede 64-bit int in VM Kairos (attualmente `int` 32-bit host). Fix VM: cambiare `int *value` in `int64_t *value` in `vm_types.h` e propagare.
- **printf width runtime**: `%Nd`/`%-Nd`/`%0Nd` via `__mn_putd_width{,_left,_zero}`, `%Nu`/`%-Nu`/`%0Nu` via `__mn_putd_uint_width{,_left,_zero}`, `%Nx`/`%-Nx`/`%0Nx` via `__mn_putx_width{,_left,_zero}`, `%No`/`%-No`/`%0No` via `__mn_puto_width{,_left,_zero}`, `%Np`/`%-Np`/`%0Np` via `__mn_putx_width{,_left,_zero}` (riusato sull'hex body, prefisso `0x` non padded). Flag `+`/` ` runtime su `%d` via `__mn_putd_plus` / `__mn_putd_space`.

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
