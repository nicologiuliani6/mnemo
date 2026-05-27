# TODO

## Bug aperti

### `c_test/des.c` — round-trip dec != plain

Status corrente (post-fix VM int64 + mnhalve unsigned + MNSPLIT32 + putx_u64):

- Print `%llx` di u64 ora corretto (MNSPLIT32 + `__mn_putx_u64`).
- u64 rotate `(key << 5) | (key >> 59)` ora corretto (mnhalve unsigned in `__mn_shr_into`).
- Subkeys keyschedule corretti (verificato `_dbg_keysched.c`).
- F() inline in main + masks (`x &= 0xFFFFFFFF` dopo ogni op) → output matcha
  gcc (verificato `_dbg_enc1.c` 16 rounds: L16=71deeadd R16=14969ffc).
- Bug residuo SCOPERTO: array locale di funzione non-main passato a callee
  NON è condiviso tra caller e callee. Es. `u32 subkeys[16]` in `encrypt()`
  vive in cell locali `__mn_v___mn_arr_subkeys_*`; chiamata `keyschedule(key, subkeys)`
  passa solo `__mn_mem*` (shared mem), non i cell locali. Keyschedule riempie
  mem cells (sbagliati), encrypt legge sub locali (zero). Repro minimal:
  `c_test/_dbg_arr3.c` (use() chiama fill() con int a[4]; a resta 0).
- Fix richiede layout_collect: local array passato a callee deve essere
  promosso a `__mn_mem*` (oppure copia in/out al call boundary).
- Bug u32 modular SEPARATO: ops in F() su u32 non maschereranno a 32-bit;
  c_lower dovrebbe tracciare tipo unsigned int e emit `& 0xFFFFFFFF` dopo
  ogni assignment. Workaround sorgente con mask espliciti.

### `--opt-uncall-user-calls` su `c_test/des.c` → POP stack vuoto

`mnemo run c_test/des.c --opt-uncall-user-calls --native-arith` →
```
[VM] POP: stack vuoto! (frame=__mn_shr_into dest=ph stack=__mn_hist inv=4)
```

- Triggered durante inverse a profondità 4 (opt-uncall stratifica).
- `__mn_shr_into` ora usa mnhalve-based push pattern; opt-uncall hist tracking
  potrebbe non riconoscere il nuovo pattern correttamente.
- `c_test/loop.c --opt-uncall-user-calls` funziona — sospetto pattern shift
  o interazione con altri helper (and_into, or_into, etc.).

### `c_test/kernel.c` — struct array runtime indexing

`mnemo run c_test/kernel.c`:
```
mnemo: &: supportati `&x`, `&struct.campo`, `&array[idx]`
```

Blockers:
- `&K.procs[K.current]` — & su array di struct con idx runtime, base StructRef.
  Mnemo c_lower attualmente supporta solo `&x`, `&struct.campo`, `&array[idx]`
  con base c.ID — non `&base.field[idx]`.
- `K.procs[idx].field = ...` con `idx` runtime — richiede pool dispatch su
  array di struct (Mnemo supporta dispatch su array di scalari, non struct).
- `process_t* p = &K.procs[idx]; p->state = X` — pointer-to-struct con
  runtime dispatch su tutti i campi.
- `strcpy(K.procs[i].mem, "init")` con `i` runtime su array di char dentro
  struct.

Fix richiede estensione layout per struct-of-array runtime + multi-target
dispatch su tutti i campi della struct element.

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
