# TODO

## Bug aperti

### opt-uncall su programmi con struct global + printf condizionale fallisce

File: `c_test/_dbg_kernel_sched.c`. Senza `--opt-uncall-user-calls`
match perfetto con gcc (3× `p0`). Con il flag:
`[VM] POP: __mn_hist sotto il pavimento mnemo (manca __mn_hist_floor_snap?)`
e nessun output.

Pattern: struct global `K` con field array di struct + printf condizionale
dentro fn user `worker(proc_t *p)` chiamata da main. show_using_targets
DOVREBBE escludere worker (transitive printf use), ma evidentemente non
sta funzionando o lo snap floor pattern non si chiude correttamente.

Workaround: omettere `--opt-uncall-user-calls` per programmi con questo
pattern.



### VM `op_uncall` su void proc con `show` → SIGSEGV (workaroundato Mnemo)

Bug VM sotto la superficie. Workaround corrente in Mnemo:
`show_using_targets` transitive closure esclude user fn con printf
da single-call opt-uncall.

**Diagnosi (post-investigazione)**: con workaround disabilitato (Mnemo
emette `call printer` + `uncall printer`), VM crash su 2° ciclo
`printer(N)`. gdb trace mostra ricorsione profonda in
`exec_branch_inverse` → `invert_op_to_line` → `clone_frame_for_depth`
→ `memset` overflow.

Causa: `__mn_putd_uint` è self-recursive. Forward stack genera frames
`__mn_putd_uint@1, @2, @3, ...` per ogni digit. Inverse rivisita
frames crescenti senza release. 2 chiamate `printer()` consecutive
accumulano depth fino a `@358`, supera `MAX_FRAMES=200`.

Workaround alternativi (testati, INSUFFICIENTI):
- Bump `MAX_FRAMES` a 1024 → overflow @982 (printf+uncall accumula
  indefinitamente).
- Depth cap via modulo → causa `get_findex: frame @N non trovato` per
  call sites che lookup chiave originale.
- ulimit -s 512MB → ancora SIGSEGV (memoria corruption, non stack OF).
- `frame_indexer_count_at_snap` save/restore + reset clone slot names
  → libera frame *tra* cicli call+uncall consecutivi, ma depth cresce
  fino @158 DENTRO un singolo inverse (commit ba177bf safety guard).
- Reset `recursion_depth = 0` su base frame ad UNCALL → non aiuta:
  la crescita @N avviene in `vm_invert.h:1212-1218` leggendo `@N` dal
  frame_name corrente, non da `recursion_depth`.

Causa profonda: `recursion_depth` mai resettato. Forward `__mn_putd_uint`
cresce depth per digit; inverse re-entrara generando frames @1..@N
incrementali. Tra cicli `call printer / uncall printer` consecutivi,
depth NON azzerato → unbounded growth.

Fix VM corretto richiede:
1. Reset `recursion_depth` su rientro a main context post-uncall.
2. O GC frames non più referenziati dopo uncall completato.
3. O refactor `vm_invert.h` mutual recursion in iterative loop.

Workaround Mnemo (`show_using_targets` exclusion) resta attivo per
correttezza. Trade-off: opt-uncall disabilitato per fn con printf.

## Lavori grossi futuri

### 1. VM Kairos: allocazione dinamica strutture interne

Oggi la VM ha caps statici hard-coded su quasi tutte le strutture runtime:

- `MAX_VARS` (var per procedura).
- `MAX_LABEL` (label per procedura).
- `MAX_NESTED` (annidamento blocchi).
- `MAX_FRAMES` (totale frame attivi nello stato VM).
- `MAX_PROC_PARAMS` (param per procedura).
- `MAX_CALL_ARGS` (arg per `call`/`uncall`).
- Stack di hist/branch a size fissa.
- Channel buffer fissi.

Conseguenze: programmi grossi o ricorsioni profonde abortano con errori
opachi (es. `frame indexer overflow`, `MAX_FRAMES exceeded`); Mnemo deve
inserire fallback (banked pools, `inline_user`) per stare sotto le soglie.

**Obiettivo**: portare tutte le strutture a allocazione dinamica
(`malloc`/`realloc` o arena growable con doubling). Caps spariscono, la
VM cresce on-demand finché c'è RAM host. Richiede:

- Refactor `vm_types.h` + tutte le `init_*`/`destroy_*`.
- `frame_indexer` da array statico a hashmap/dynarray.
- Hist/branch/loop stack growable (path con copia su realloc, attenzione
  a puntatori salvati).
- Channel queue growable.
- Update `kairos_limits.py` lato Mnemo: rimuove i guard check, lascia
  solo i fallback opzionali su user request.

### 2. Mnemo: pointer pool runtime growable (auto-sizing già fatto)

**Già fatto**: pool size auto-inferito da `_infer_ptr_pool_size` che
conta call site di `malloc`/`calloc` nel sorgente. Default `--ptr-pool-size 4`
è ora un *minimo*; auto-cresce verso l'alto se servono più slot. Banked
pools scattano sopra `MONOLITHIC_POOL_MEM_MAX`.

**Open**: pool runtime growable (non statico al compile-time). Programmi
con `malloc` dentro un loop con N iterazioni runtime non sono inferibili
staticamente; oggi richiedono `--ptr-pool-size N_max`. Una primitiva VM
`pool_grow N` reversibile permetterebbe crescita on-demand. Dipende da
[[1. VM Kairos: allocazione dinamica strutture interne]].

---

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
