# TODO

## Bug aperti

### `c_test/des.c` — round-trip dec != plain

Status (post-fix u32 mask `__mn_mask_u32` lib helper):

- `%llx` u64 OK (MNSPLIT32 + `__mn_putx_u64`).
- u64 rotate `(key << 5) | (key >> 59)` OK (mnhalve unsigned in `__mn_shr_into`).
- Subkeys keyschedule OK (verificato `_dbg_keysched.c`).
- u32 modular semantics OK: AST pass auto-inserisce `__mn_mask_u32(x)` dopo
  ogni assignment a var u32; helper basato su mnsplit32 (O(1) VM op).
- **`des.c` round-trip `dec == plain` OK** (cipher però differisce da gcc
  per bug local-array passing — vedi sotto).
- **Workaround `des_global.c`**: subkeys promosso a global `g_sub[16]` →
  cipher e dec corretti, matcha gcc esattamente.

Bug aperti:

1. **Local array passing**: `u32 subkeys[16]` in `encrypt()` (non-main) non è
   condiviso con callee `keyschedule`. Local cells `__mn_v___mn_arr_subkeys_*`
   vivono in caller; callee scrive su mem cells diversi. Repro: `c_test/_dbg_arr3.c`
   (use() chiama fill(int a[4]); a resta 0).
   Fix: `layout_collect` deve promuovere array locali non-main passati come
   parametro a `__mn_mem*` slot, oppure inserire copia in/out al call boundary.
   Effetto: cipher Mnemo differisce da gcc (round-trip dec=plain però OK
   perché bug simmetrico per encrypt e decrypt).
2. **`--opt-uncall-user-calls` + arith helpers → POP empty**:
   `mnemo run c_test/des.c --opt-uncall-user-calls --native-arith` →
   `[VM] POP: stack vuoto! (frame=__mn_shr_into dest=ph stack=__mn_hist inv=4)`.
   Pattern shr_into (mnhalve-based) hist tracking probabile non riconosciuto
   da opt-uncall. `c_test/loop.c --opt-uncall-user-calls` OK; sospetto
   interazione con and_into/or_into/shr_into nested in user fn.
   Fix: diff `.kairos` loop vs des, individuare divergenza opt-uncall snapshot
   pattern.

### `c_test/kernel.c` multithread: layout memoria troppo grande per pthread ABI

Dopo fix `init_mutexes(&K.channel)` + `&K.channel` (sub-struct) + parallel2
ABI flessibile (1 arg per worker0, 2 per worker1), Mnemo errore:
```
mnemo: layout memoria troppo grande per le `call` Kairos con ABI pthread:
riduci celle / ptr pool oppure evita mnemo_pthread_* in questo file.
```

Causa: kernel.c globale `K` con `process_t procs[4]` (4×67 cells per
campo pid/state/pc + char mem[64]) + `mps_t channel` + answer locali
supera `KAIROS_MAX_CALL_ARGS`. Inline_user normalmente collassa, ma
disabilitato in presenza di pthread (ABI two-region par).

Fix: o ridurre dimensione mem[64] → mem[16] in kernel.c, o estendere
`maybe_inline_user_functions` per supportare pthread (inlinare callees
non-pthread). Strategicamente: layout banking, o split mem buffers in
strutture esterne (`__mn_pool_*`).

### `mnemo_pthread_parallel2` su mps.h con kloop a 2 params (1° ignorato)

`c_test/kernel.c` multithread:
```c
void kloop(mps_t *mps, int *unused) { ... }
void kernel_recv(mps_t *mps, int *answer) { ... }
mnemo_pthread_parallel2(kloop, kernel_recv, &K.channel, &K.channel, &answer);
```
mps.h's macro accetta `void (*)(mps_t*, int)` come worker e chiama solo `fn(mps)`
ignorando il secondo arg. Mnemo invece pretende N args dove N = numero param
di ciascun worker (qui 2+2 = 4 worker args). User passa 3, Mnemo errore.

Fix: estendere parser parallel2 per riconoscere il pattern asimmetrico mps.h
(a: 1 arg, b: 2 args). O fornire `mnemo_pthread_parallel2_async` con ABI
flexible. O auto-detect quando worker decl ha 2 params ma callsite ne dà 1.

### Nested array dentro struct-array element con idx runtime

- Read `B.arr[i].buf[0]` (campo nested array dentro struct-array elem con i
  runtime) → `campo 'buf' assente`.
- `printf("%s", B.arr[i].buf)` con i runtime → "letterale … o char*".
  Stesso scope — nested char[] field read tramite dispatch non implementato.

Fix: estendere `_disj_eq_chain` su struct-array per dispatch su campi
nested array; e printf %s dispatch su char[] tramite struct-array.

### VM `op_uncall` su void proc con `show` → SIGSEGV (workaroundato Mnemo)

Bug VM sotto la superficie. Workaround corrente in Mnemo:
`show_using_targets` transitive closure esclude user fn con printf
da single-call opt-uncall.

Fix VM corretto: `vm_invert.h` / `op_uncall` deve gestire void proc con
`show` ops senza crashare. Permette di ri-abilitare opt-uncall per fn
con printf (perf gain). Indagare inverse di INVOP_SHOW + interaction
con `call __mn_putd`.

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
