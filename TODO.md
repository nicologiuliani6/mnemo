# TODO

## Bug aperti



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

**Tentativo 2026-05-30 (FALLITO)**: cap globale `VM_MAX_SAFE_DEPTH=256`
in `clone_frame_for_depth`. Evita CHAR_ID_MAP overflow ma causa infinite
loop perché branch replay logic in `invert_op_to_line:1129-1149` continua
a riapplicare ELSE+THEN su stesso frame riusato senza terminazione.

Il branch replay si basa su `vm->frames[fi].recursion_depth` per sapere
quante ELSE iter ricreare. Per frame creati SOLO in inverse, `.rd=0`
default → fallback a `do_eval_if_entry` → eval cond → pick branch
(potenzialmente THEN sbagliato → ricorsione infinita).

Fix corretto richiede tracciare quanti livelli forward sono stati
effettivamente eseguiti per OGNI frame, non solo il base. Lavoro non
banale; defer.

Workaround Mnemo (`show_using_targets` exclusion) resta attivo per
correttezza. Trade-off: opt-uncall disabilitato per fn con printf.

### IF/FI reversibilità rotta per `if (arr[k]==x) arr[k]=y;` con k costante (FIXATO 2026-05-31)

**Root cause**: `_transform_hoist_unsafe_if_conds` rilevava solo
assegnazioni con lvalue `c.ID`. Pattern `arr[k] = v` con lvalue
ArrayRef veniva ignorato → cond `arr[k] == c` con body che muta
`arr[k]` non veniva hoisted → IF/FI guard sulla cella `__mn_memX`
direttamente → VM error "IF/FI non reversibile".

**Fix** (compile.py:_lvalue_base_ids): estrae ID base anche da
ArrayRef/StructRef/UnaryOp deref. Body writes ora include `arr` per
`arr[k] = v`, `p->field = v`, `*p = v`, `s.f = v`. Hoist scatta.

### opt-uncall + loop + if con self-mut → DELOCAL/POP error (WORKAROUND 2026-05-31)

Pattern: fn con `for/while/do { if (E_self_mut) BODY_self_mut }`.
Anche con hoist applicato (cond stabile via fresh int), opt-uncall
inverse rompe lifecycle di `__mn_lc1` (loop counter local):
- forward: `local lc1=0; lc1 += e0; if lc1!=0 then [body] fi; push(lc1,hist)`
- inverse: `pop(lc1)`, `inverse if`, `lc1 -= e0`. e0 in inverse non
  recupera valore originale (consumato da push/pop loop body) →
  `lc1 -= 0` invece di `lc1 -= 1` → lc1 = 1 a delocal (atteso 0).
- VM error: `DELOCAL: valore finale errato! var=__mn_lc1, atteso=0, trovato=1`
  oppure `POP: __mn_hist sotto il pavimento mnemo`.

**Workaround** (c_lower.py:loop_hoist_targets): hoist transform
ritorna set di fn dove ha sparato dentro un loop body. Queste fn
escluse da `apply_uncall_opt` / `apply_void_uncall_opt`.

**Fix corretto** richiede investigare l'interazione tra inverse di
`from cond loop body until cond2` (kairos) e la riallocazione di
e0 cross-iter quando il body esegue push(e0,hist) + ricomputa e0.

## Lavori grossi futuri

### 1. VM Kairos: allocazione dinamica strutture interne (parziale)

**Già dinamici**:
- `vm->frames` (era `[MAX_FRAMES=200]`) → heap, cresce on-demand
  via `vm_ensure_frame_cap` (init=256, raddoppia).
- `CallRecord *cs` in vm_run_BT cresce dinamicamente.
- `vm->branch_trace` (era `[VM_BRANCH_TRACE_MAX=131072]`) → heap,
  raddoppia in op_jmpf.
- `IF_BRANCH_STACK_MAX` bumped 256→65536 (thread-local stack).
- `vm->mn_hist_floor_snaps` (era `[MNEMO_HIST_SNAP_DEPTH=384]`) → heap,
  raddoppia in CALL __mn_hist_floor_snap (commit 2026-05-31).
- `Var.value` (TYPE_STACK) e `Channel.buf`: `VAR_STACK_MAX_SIZE=512` e
  `VAR_CHANNEL_MAX_SIZE=128` sono solo alloc INIZIALE; tutti i push
  fanno `realloc(stack_len+1)` per-elemento (no hard cap, però perf
  subottimale: refactor a doubling amortizzato è auspicabile).

**Open — limiti Frame statici** (in struct, non triviali da rendere dyn):
- `MAX_VARS=2048`, `MAX_LABEL=8192`, `MAX_NESTED=1024`, `MAX_PROC_PARAMS=1024`,
  `VM_TRACE_WIN_STACK_MAX=4096`.
- Bump > 1024 di MAX_NESTED causa Frame size > 600KB → realloc di
  `vm->frames` (pointer array) sposta i Frame objects → invalida
  pointer-into-frame held da operazioni cross-call (ex33 parallel2_fib
  SIGSEGV).
- **Fix corretto**: refactor `vm->frames` da `Frame *frames` a
  `Frame **frames` (array di pointer a Frame heap-alloc separati). Così
  realloc del pointer array non sposta i Frame individuali. Richiede
  cambiare ~288 access site `vm->frames[i].x` → `vm->frames[i]->x` (sed
  bulk fattibile ma rischioso).

**Open — non ancora toccati**:
- DBG_MAX_BREAKPOINTS=256, DBG_MAX_HISTORY=4096 (debug only, low priority).

Update `kairos_limits.py` lato Mnemo per allinearsi a quanto cambia.

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
