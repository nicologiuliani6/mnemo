# TODO

## Note / feature

### `--check-invertibility` + `--vm-dump`: dump dello stato forward (DONE)

Prima il VM dump usciva vuoto (o non usciva affatto) con
`--check-invertibility`: il wrapper `main` fa `call __main__ ; uncall
__main__`, l'uncall reverte tutto e il `vm_dump` finale (post-uncall)
trova memoria azzerata; se l'uncall fallisce (es. `kernel` con
ssend/channel → `[VM] SSEND: destinazione non è channel!`) la VM esce 1
prima del dump.

Fix: nuovo builtin Kairos `dump()` → opcode `DUMP` (`vm_dump_active`,
dump del frame attivo via `get_findex`). Mnemo lo inietta in coda a
`__main__` (blocco `__mn_inv_dump`), PRIMA dei delocal e dell'uncall →
stato forward sempre stampato. `DUMP` è no-op nell'inverso (`INVOP_DUMP`)
e soppresso durante replay (`suppress_show`). Flag `vm->mn_dumped` salta
il dump finale post-uncall (evita doppio header).

**Caveat native-arith nell'inversione**: con native-arith ON (Janus.c
UNCALL path `mn_native_arith_uncall_inverse`), `--check-invertibility`
verifica l'inverso C nativo O(1) di mul/divmod/bits, NON la reversibilità
del codice Kairos di `mul.kairos`/`divmod.kairos`/`bits.kairos`. Per
stressare il lib-code reversibile vero → check-invertibility SENZA
native-arith.

## Bug aperti



### Follow-up: rilassare workaround `show_using_targets` (post put-skip)

Ora che l'inverse di `call __mn_put*` è no-op (put-skip in `vm_invert.h`),
il workaround Mnemo `show_using_targets` — che esclude le fn-con-printf da
opt-uncall **dentro loop** (`show_blk = name in show_using_targets and
bool(ctx.loop_stack)`, c_lower.py ~7595) — potrebbe non servire più.
Verificare se le call printer-in-loop opt-uncall ora invertono pulite; se
sì, rimuovere l'esclusione. Safety-net residuo: cap `MN_CLONE_MAX_DEPTH=512`
in `clone_frame_for_depth`.

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

**Blocca anche `--check-invertibility` whole-program**: dopo il put-skip,
DES supera putd ma fallisce su `DELOCAL: __mn_lc0 atteso=0 trovato=-1`
(frame=decrypt) — stessa classe (inverse del loop counter sotto `uncall
__main__` plain). È ora il prossimo blocker per la verifica reversibilità
di programmi con loop non banali.

**Reproducer minimi (2026-05-31, plain uncall __main__)**:
- OK: loop semplice accumulo `for(i=10;i>0;i--) s+=i;` → inverte (exit 0).
- OK: `while(i<N){ emit(i); i++; }` con printf → inverte (post put-skip).
- OK (RISOLTO 2026-05-31): `g[i]=...` store runtime-index (disj-chain
  `if i==0 .. else if i==1 ..`), singolo o in loop `for(i) g[i]=i*i`.
  Root cause era **Kairos** `exec_branch_inverse` (vm_invert.h): la
  else-if chain annida ogni IF nell'ELSE del precedente; lo scan reverse
  dispatchava OGNI nested IF nello span (non solo il figlio immediato) →
  C2,C3,… invertiti sia al top-level sia via recursion del parent →
  doppia inversione → `POP: stack vuoto` su `__mn_hist`. Fix Kairos
  commit 5098d1f: skip candidate enclosed da un altro nested IF dello span.
- OK (RISOLTO 2026-05-31): multi-disj-chain + compound-read: ≥3 store
  `g[k]=v` seguiti da `g[a]+=g[b]` (6 disj-chain ≈ 36 nested IF). Root
  cause era **Kairos** `MAX_IFS=32`: `collect_ifs` troncava i frame con
  molte disj-chain → IF-map parziale → branch-pairing errato → `POP:
  stack vuoto`. Fix Kairos commit c5b56ae: MAX_IFS→256 + heap-alloc del
  local `ifs[]` in `exec_branch_inverse`. Regression guard
  `c_test/inv_multi_disjchain_compound.c` (ora inverte). Limite residuo
  noto: `collect_ifs` `stack_idx[64]` capa la *profondità* di nesting a
  64 → indice runtime su array più lunghi di 64 ancora rotto.
- OK (RISOLTO 2026-05-31): loop annidato
  `while(i<4){while(j<4){g[i]^=j;j++;}i++;}` → era `SIGSEGV` (exit -11).
  Indipendente da array/disj-chain: anche `while{while{s+=j}}` crashava.
  **Root cause (valgrind)**: use-after-free in `exec_branch_inverse`
  (vm_invert.h). Lo snapshot `saved[] = vars[]` veniva reinstaurato a fine
  branch con `memcpy(vars, saved)` *intero*; ma `op_local`/`op_delocal`
  fanno `free`+`realloc` del Var, quindi i puntatori che il branch
  liberava (es. `delocal lc` di un loop counter) restavano dangling in
  `saved[]`. Sotto la recursion annidata `exec_branch_inverse →
  invert_op_to_line → exec_branch_inverse` il livello interno salvava il
  tmp Var dell'outer, lo liberava via op_local, e il blanket restore lo
  reinstaurava → UAF al successivo op_local. Fix Kairos commit 79ab8fe:
  lo snapshot serve solo a sganciare gli slot **param** (relink temporaneo
  al caller); restore SOLO quelli, lascia agli altri slot l'esito reale
  del branch. Valgrind clean. Regression guard `c_test/inv_nested_loop.c`.
Il forward + run normale di questi pattern funziona; solo
`--check-invertibility` (uncall whole-program) li espone. **Tutti i
reproducer minimi noti ora invertono** (resta il limite di profondità
disj-chain >64 sopra).

**Workaround** (c_lower.py:loop_hoist_targets): hoist transform
ritorna set di fn dove ha sparato dentro un loop body. Queste fn
escluse da `apply_uncall_opt` / `apply_void_uncall_opt`. Stesso set
copre anche le fn con cond-hoisted contenente TernaryOp (il `?:` genera
un IF interno con push/pop hist → inverse sbilancia anche fuori loop;
vedi regression generic_if_ternary_index.c).

**Fix corretto** (opt-uncall loop-counter, ancora aperto) richiede
investigare l'interazione tra inverse di `from cond loop body until cond2`
(kairos) e la riallocazione di e0 cross-iter quando il body esegue
push(e0,hist) + ricomputa e0. Nota: il sotto-caso disj-chain runtime-index
NON era questo — era il bug Kairos `exec_branch_inverse` (else-if chain
double-dispatch), risolto in commit Kairos 5098d1f. Restano aperti i due
FAIL residui sopra (multi-disjchain compound-read, nested-loop SIGSEGV).

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
- **`vm->frames` ora `Frame **`** (commit Kairos 3036648, 2026-05-31):
  Frame allocati individualmente sull'heap → realloc del pointer array
  non sposta Frame. Sblocca bump safe di MAX_NESTED/MAX_VARS senza
  rompere ex33 parallel2_fib.

**Open — Frame fields statici**: bumping ora safe (no Frame movement),
ma richiede per-Frame realloc inline + sed dei field access:
- `MAX_VARS=2048` (Var *vars[]), `MAX_LABEL=8192` (uint label[]),
  `MAX_NESTED=1024` (loop_restart_i/loop_bottom_i),
  `MAX_PROC_PARAMS=1024` (param_indices[]),
  `VM_TRACE_WIN_STACK_MAX=4096` (trace_window_stack[]).
- Bump statico ora possibile senza crash; dyn alloc per future-proof.

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

### 3. C-subset: `arr[i].campo` su array-di-struct top-level (non supportato)

`_structref_base_and_path` (c_lower.py:~2879) esige che la base di `.campo`
sia un `c.ID`. Per `P arr[3]; arr[i].x = v;` la base è un `c.ArrayRef` →
errore `la base di .campo deve essere un identificatore`. Fallisce anche
con indice **costante** (`arr[0].x`). Esiste già infra per array-di-struct
annidati (`struct_array_info`, synth tag `__elem` in `_resolve_struct_array_meta`),
ma il path StructRef→ArrayRef base non è agganciato.

Fix: in `_structref_base_and_path` accettare base `ArrayRef`; calcolare la
cella `base + idx*sizeof(elem) + field_offset`. Indice costante = cella
diretta (`arr__N__campo`); indice runtime = riusare la disj-chain / pointer
arith come per `arr[i]` scalare. Repro: stress s9 (`/tmp/s9.c`), atteso
gcc `0 20 20`. Non bloccante (pattern raro, scoperto in stress interno).

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
