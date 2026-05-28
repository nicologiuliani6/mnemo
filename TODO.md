# TODO

## Bug aperti

### `c_test/des.c` — round-trip dec != plain

Status (post-fix VM int64 + mnhalve unsigned + MNSPLIT32 + putx_u64):

- `%llx` u64 OK (MNSPLIT32 + `__mn_putx_u64`).
- u64 rotate `(key << 5) | (key >> 59)` OK (mnhalve unsigned in `__mn_shr_into`).
- Subkeys keyschedule OK (verificato `_dbg_keysched.c`).
- F() inline in main + masks → output matcha gcc (verificato `_dbg_enc1.c`
  16 rounds: L16=71deeadd R16=14969ffc, dec round-trip OK).
- **Workaround `des_global.c`**: subkeys promosso a global `g_sub[16]` →
  cipher e dec corretti (matcha gcc).
- **`des.c` originale `dec != plain`**: oltre ai sub-bugs sotto, anche output
  non riesce. Repro: `make run FILE=c_test/des.c MAIN_ARGC=0` con o senza
  `--native-arith`.

Bug aperti:

1. **u32 modular semantics**: ops in F() su u32 non mascherano a 32-bit. c_lower
   deve tracciare tipo unsigned int e emit `& 0xFFFFFFFF` dopo ogni op
   aritmetica/shift/xor. Senza mask, valori int64 cell crescono oltre 2^32.
   Workaround sorgente con mask espliciti già necessario in `_dbg_enc1.c`.
   Fix: estendere `c_lower.py` per detection u32 type e inserire IAndEq
   con maschera dopo BinaryOp/UnaryOp che producono u32.
2. **Local array passing**: `u32 subkeys[16]` in `encrypt()` (non-main) non è
   condiviso con callee `keyschedule`. Local cells `__mn_v___mn_arr_subkeys_*`
   vivono in caller; callee scrive su mem cells diversi. Repro: `c_test/_dbg_arr3.c`
   (use() chiama fill(int a[4]); a resta 0).
   Fix: `layout_collect` deve promuovere array locali non-main passati come
   parametro a `__mn_mem*` slot, oppure inserire copia in/out al call boundary.
3. **`--opt-uncall-user-calls` + arith helpers → POP empty**:
   `mnemo run c_test/des.c --opt-uncall-user-calls --native-arith` →
   `[VM] POP: stack vuoto! (frame=__mn_shr_into dest=ph stack=__mn_hist inv=4)`.
   Pattern shr_into (mnhalve-based) hist tracking probabile non riconosciuto
   da opt-uncall. `c_test/loop.c --opt-uncall-user-calls` OK; sospetto
   interazione con and_into/or_into/shr_into nested in user fn.
   Fix: diff `.kairos` loop vs des, individuare divergenza opt-uncall snapshot
   pattern.

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

### ~~`c_test/kernel.c` — struct array runtime indexing~~ ✅ RISOLTO

`mnemo run c_test/kernel.c` matcha output gcc. Subtask completati:

1. ✅ `&base.field[const]` parser (c_lower.py): supporta `&K.procs[const]`.
2. ✅ Runtime R/W `K.procs[i].field` con i runtime: già supportato via
   `_disj_eq_chain` in c_lower (read line 5057, write line 8505).
3. ✅ Fat pointer `process_t* p = &K.procs[i]`: AST rewrite
   `_transform_struct_array_pointer_alias` in compile.py — `p` diventa
   int holding idx, `p->f` riscritto a `K.procs[p].f`. Cross-fn:
   parametri `T*` di funzioni con T = struct-tag file-scope-unico
   promossi ad alias.
4. ✅ `strcpy(K.procs[i].mem, "init")` con i runtime: già funzionante.
5. ✅ Bonus: `_transform_return_in_loop` esteso a void function con
   bare `return;` (richiesto da `void schedule()`).

Bug residui osservati:

- Read `B.arr[i].buf[0]` (campo nested array dentro struct-array elem con i
  runtime) → `campo 'buf' assente`. Non blocca kernel.c (non usa pattern).
- `printf("%s", B.arr[i].buf)` con i runtime → "letterale … o char*".
  Stesso scope — nested char[] field read tramite dispatch non implementato.

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
