# TODO

## OPEN

### [P3] opt-uncall su callee recursive — DEFERRED (guard esteso)

`--opt-uncall-user-calls` su call site la cui callee è recursiva (diretta o
indiretta) crasha durante uncall con `POP: stack vuoto! frame=fib@N`.

Root cause: VM `invert_op_to_line` JMPF_ELSE handler (vm_invert.h:1080-1101)
usa `vm->frames[fi_reset].recursion_depth` come "replay count" del ramo ELSE.
Il count rappresenta la profondità totale del frame in nesting, NON quante
volte ogni branch (ELSE vs THEN) è stato preso forward. Per fib(N), THEN
branch viene preso 1 volta (base case) e ELSE N-1 volte. Replay ELSE depth=N
sovraconta → pop oltre i push reali.

Tentato Strada A (VM flag self_rec single-replay): NON funziona perché:
1. Il problema affligge anche call non-self-rec da main verso callee recursive.
2. Single replay (depth=1) non corregge: frame.recursion_depth resta
   conteggio errato per non-self-rec callers.

Guard esteso in c_lower.py: `apply_uncall_opt`/`apply_void_uncall_opt` ora
bloccano sia `self_rec` sia `callee_recursive`
(via `_func_is_recursive_user`). Trade-off: opt-uncall skip per qualsiasi
call site la cui callee si auto-chiama. fib(8), gcd, divmod_signed coperti
dal fallback non-opt.

Fix definitivo richiede: VM tracks per-branch entry counts (THEN/ELSE) per
frame depth, oppure Mnemo emit manual XOR inversion per call site con callee
recursive (skipping uncall pattern). Stima 6-10h + design review.

---

## C-subset features ancora da implementare

### Stdlib

- **`<string.h>`** runtime: `strlen` / `strcmp` compile-time su literal/`char *p
  = "lit";`. `memcpy(dst, src, N)` / `memset(dst, v, N)` espansi a compile-time
  se dst (e src) sono array Mnemo e N costante. Ora anche `strcpy(dst, src)`,
  `strncpy(dst, src, N)` e `memmove(dst, src, N)` compile-time-expanded con dst
  array Mnemo (src letterale o char[]). Caso completamente runtime (dst dinamico,
  N runtime) richiede loop variable-length non rappresentabile reversibilmente
  con bound staticamente noto.

### Control flow / misc

- **`return` dentro `if`/`switch`/loop**: pre-pass `_transform_switch_returns`, `_transform_if_chain_returns`, `_transform_early_return_if_then_return`, `_transform_general_early_returns` e `_transform_return_in_loop` coprono: switch-only, if/else-chain-only, body con `if(c) return E;` come primo stmt + return finale, qualsiasi numero di stmt prima/dopo `if(c) return E;` (cascade ricorsivo, cond snap in `__mn_g_k`), e return dentro for/while/do-while (return-flag `__mn_rf5_k` + body wrap in `if (!flag)` + loop cond estesa con `&& !flag`).

### printf

- **printf `%u` runtime su valori negativi**: stampa la rappresentazione signed (non `2^32 + val`). VM int64 ora supporta cell > INT_MAX (commit kairos `feat(vm): cell value e channel buf da int → int64_t`). Mnemo emit `if cell < 0 then cell += 2^32` resta bloccato finché `__mn_divmod_nonneg` (sottrazione ripetuta, O(n)) non ha algoritmo sub-lineare — per n=2^32 servirebbero ~4G iterazioni. Fix futuro: divmod binario reversibile (loop fisso 32 iter).
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
