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



### VM `op_uncall` su void proc con `show` → divergenza inverse putd/putx (RISOLTO 2026-05-31)

**RISOLTO** (commit Kairos put-skip): l'inverse di `call __mn_put*`
(putd/putx/puto + varianti) è ora un no-op (`vm_invert.h` INVOP_CALL:
`if (strncmp(pn,"__mn_put",8)==0) skip`). Corretto perché i printer sono
identità sullo stato (divmod self-uncalled, show no-op, locali delocal'd →
net `__mn_hist`=0). Elimina la ricorsione inversa non-terminante. Verificato:
`--check-invertibility` su printf-in-loop ora inverte (exit 0), prima hang.
Il cap `MN_CLONE_MAX_DEPTH=512` resta come safety-net per altri runaway.

**Da investigare (follow-up)**: ora che l'inverse di putd è no-op, il
workaround Mnemo `show_using_targets` (esclusione fn-con-printf da opt-uncall
dentro loop) potrebbe essere rilassabile/rimovibile — verificare se le
call printer-in-loop opt-uncall ora invertono pulite.

--- diagnosi storica (pre-fix) ---

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

Workaround Mnemo (`show_using_targets` exclusion) **ristretto** alle
call-site dentro loop (2026-05-31). Le call sequenziali fuori loop ora
ricevono opt-uncall: il `frame_indexer_floor_to_restore` (VM, Janus.c)
libera i frame `__mn_putd_uint@N` tra cicli call+uncall consecutivi.
Solo dentro un loop la depth si accumula cross-iter → hang; quelle
restano escluse.

Implementazione: `show_blk = name in show_using_targets and bool(ctx.loop_stack)`
(c_lower.py ~7595). Verificato byte-per-byte no-opt == opt su
kernel/des/encrypt/PC/_dbg_kernel_sched.

**Diagnosi strutturale (2026-05-31)**: il fallback recursion_depth-replay
(`vm_invert.h` ~1130) assume struttura ricorsiva "N×ELSE poi 1×THEN"
(divmod-like: il caso base è il THEN). `__mn_putd_uint` / `__mn_putx_uint`
hanno struttura OPPOSTA: "1×THEN (con `call` ricorsivo) per livello, poi
base ELSE". Il replay quindi forza il ramo THEN ad ogni livello → l'inverse
clona `__mn_putd_uint@1,@2,@3,…` senza mai raggiungere il base case →
crescita illimitata (verificato: depth incrementa 1,2,3,… linearmente,
RSS +350 MB/s). Il branch_trace preciso (corretto) è attivo SOLO per
opt-uncall di una singola proc, non per la `uncall __main__` plain del
`--check-invertibility`.

**Mitigazione (2026-05-31, commit cap)**: `MN_CLONE_MAX_DEPTH=512` in
`clone_frame_for_depth` → `vm_debug_panic` (exit 1) se la profondità
supera 512. NB: diverso dal tentativo modulo-256 fallito (che RIUSAVA i
frame → loop infinito); questo ABORTISCE pulito. Profondità reale forward
≪ 512 (cifre ≤ 19, divmod mnhalve ≤ 64) → mai falsi positivi (199 test
verdi). Effetto su `--check-invertibility` di programmi con printf:
dump+stats+output forward escono (stampati PRIMA dell'uncall), poi
l'uncall abortisce con messaggio chiaro invece di hang/OOM. DES passa da
hang-infinito a 4 s + errore diagnostico.

**Risolto** dal put-skip (vedi banner in cima alla sezione): non serve più
né branch_trace whole-program né rewrite non-ricorsivo di putd. Il cap
resta come safety-net.

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

**Reproducer minimi (2026-05-31, plain uncall __main__)** — falliscono
puliti (exit 1, no hang):
- OK: loop semplice accumulo `for(i=10;i>0;i--) s+=i;` → inverte (exit 0).
- OK: `while(i<N){ emit(i); i++; }` con printf → inverte (post put-skip).
- FAIL `g[i]=i*i` in loop (indice=counter): `POP: stack vuoto dest=__mn_mem8`
  — disj-chain runtime-index spinge hist solo nel ramo che matcha; l'inverse
  pop sbilanciato sotto uncall plain.
- FAIL loop annidato `while(i<4){while(j<4){g[i]^=j;j++;}i++;}`:
  `DELOCAL __mn_lc1 atteso=0 trovato=-2`.
Bug distinti del plain-uncall inverse (loop counter lifecycle + disj-chain
hist balance). Il forward + run normale di questi pattern funziona; solo
`--check-invertibility` (uncall whole-program) li espone.

**Workaround** (c_lower.py:loop_hoist_targets): hoist transform
ritorna set di fn dove ha sparato dentro un loop body. Queste fn
escluse da `apply_uncall_opt` / `apply_void_uncall_opt`. Stesso set
copre anche le fn con cond-hoisted contenente TernaryOp (il `?:` genera
un IF interno con push/pop hist → inverse sbilancia anche fuori loop;
vedi regression generic_if_ternary_index.c).

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
