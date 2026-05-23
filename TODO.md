# TODO

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

- **printf width runtime**: `%Nd`/`%-Nd`/`%0Nd` via `__mn_putd_width{,_left,_zero}`, `%Nu`/`%-Nu`/`%0Nu` via `__mn_putd_uint_width{,_left,_zero}`, `%Nx`/`%-Nx`/`%0Nx` via `__mn_putx_width{,_left,_zero}`, `%No`/`%-No`/`%0No` via `__mn_puto_width{,_left,_zero}`, `%Np`/`%-Np`/`%0Np` via `__mn_putx_width{,_left,_zero}` (riusato sull'hex body, prefisso `0x` non padded). Flag `+`/` ` runtime su `%d` via `__mn_putd_plus` / `__mn_putd_space`. `%u` runtime su valori negativi: sign-fix wrap (`if cell<0 then cell += 2^32`) + `__mn_putd_uint_fast` che usa `__mn_divmod_nonneg_fast` (sub-lineare via opcode VM `MNHALVE` O(1) halving) — stampa correttamente unsigned 32-bit interpretation (es. -1 → 4294967295).

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
