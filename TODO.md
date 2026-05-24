# TODO

## Bug aperti

### `--opt-uncall-user-calls` su `c_test/des.c` → DELOCAL valore errato

`mnemo run c_test/des.c --opt-uncall-user-calls` fallisce con:
```
[VM] DELOCAL: valore finale errato! (frame=keyschedule var=__mn_lc1, atteso=0, trovato=2, c_val=0)
```

- `keyschedule` ha `for(i=0; i<16; i++)` con body che chiama helper Mnemo (`__mn_shl_into`, `__mn_or_into`, `__mn_and_into`, `__mn_pool_store`).
- `__mn_lc1` (entry-flag del for, max 1 in forward) viene trovato a 2 al delocal → contaminazione hist o snapshot non protegge correttamente.
- Senza il flag: `des.c` gira (exit=0) ma output `cipher: x` strano (probabile bug separato lato emit, non VM).
- `c_test/loop.c --opt-uncall-user-calls` funziona — sospetto: chiamate ai helper dentro body loop inquinano `__mn_hist` in modo non bilanciato in uncall.
- Indagine richiede log `inv_depth` al panic per distinguere forward vs reverse run; primo tentativo di aggiungere log a Kairos `vm_ops.h` ha causato hang inatteso, rollback fatto.

Prossimi passi:
1. Re-strumentare panic con `inv_depth` + dump primi N entry di `__mn_hist`.
2. Diff strutturale tra `loop.kairos` (works) vs sezione `procedure keyschedule` in `des.kairos`.
3. Verificare se `__mn_pool_store`/`__mn_and_into`/`__mn_shl_into` lasciano residui su `__mn_hist` non riassorbiti nel reverse del chiamante.

### Overflow / output strano in `c_test/des.c` senza opt

`mnemo run c_test/des.c` (no flag) termina exit=0 ma stampa:
```
plain : 123456789abcdef0
cipher: x
dec   : 7ff7ede1718e2635
```

- `cipher: %llx` stampa `x` da solo → emit del `printf` per `unsigned long long` rotto su valore alto (possibile overflow cell 64-bit a 32-bit, oppure `__mn_putx`/`__mn_putx_width` non gestisce il valore grande).
- `dec` ≠ `plain` → encrypt/decrypt non round-trip → bug semantico in DES (rotazioni `<<5 | >>(64-5)` su `u64` con cell int64_t, possibile sign-extension o mask mancante).
- Indagare:
  1. `lib/putx.kairos` / `__mn_putx` per valori > 2^31.
  2. Lowering di `u64` shift in `c_lower.py`: `(key << 5) | (key >> 59)` con `key` cella `int64_t` — controllare mask intermedie.
  3. Confronto gcc vs mnemo su un caso ridotto (`u64 x = 0x...; printf("%llx\n", x)`).

## Librerie standard C implementabili in Mnemo

Funzioni C standard compatibili modello reversibile, realizzabili dato che
già abbiamo `malloc`/`free`, `printf`/`putchar`/`puts`, `memcpy`/`memset`/
`strcpy`/`strncpy`/`memmove` compile-time, `strlen`/`strcmp` compile-time,
variadic via `<stdarg.h>`, ptr_pool, struct/union, int64 cell.

### stdlib.h

- **`int abs(int)` / `long labs(long)` / `long long llabs(long long)`** — `if x<0 then -x else x`. Reversibile diretto.
- **`div_t div(int, int)` / `ldiv` / `lldiv`** — struct quoziente+resto. Wrapper su `__mn_divmod_signed`.
- **`void abort(void)`** — emit "abort\n" + halt.
- **`int atoi(const char *)`** — compile-time su letterale (analogo `strlen` compile-time esistente).

### string.h aggiuntivi

- **`char *strcat(char *dst, const char *src)` / `strncat(dst, src, N)`** — compile-time se dst array Mnemo, src letterale o char[]. Append byte-per-byte.
- **`char *strchr(const char *s, int c)` / `strrchr(s, c)`** — compile-time su letterale: ritorna indice/NULL.
- **`char *strstr(const char *haystack, const char *needle)`** — compile-time su letterali. Naive search.
- **`int memcmp(const void *a, const void *b, size_t N)`** — compile-time se entrambi array Mnemo + N const. Confronto byte-wise.
- **`size_t strspn` / `strcspn(s, accept)` / `char *strpbrk(s, accept)`** — char-class compile-time su letterali.
- **`char *strdup(const char *s)`** (POSIX/C23) — alloca via ptr_pool + memcpy compile-time. Solo se src letterale.

### stdio.h aggiuntivi

- **`int snprintf(char *buf, size_t N, const char *fmt, ...)` / `sprintf(buf, fmt, ...)`** — compile-time fmt parsing (analogo a `printf` esistente). Scrive in buf array Mnemo.

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
