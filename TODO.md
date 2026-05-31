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
  noto: indice runtime `g[i]` su array > ~64 elementi fallisce **pulito**
  (exit 1, no crash) sotto --check-invertibility. La disj-chain è profonda
  quanto l'array; `collect_ifs` `stack_idx[64]` la tronca. NON bumpabile
  in isolamento: alzare quel cap fa ricorrere `exec_branch_inverse` più in
  profondità e sbatte sui cap successivi (`MAX_LINES=1024`, MAX_IFS, stack
  di ricorsione) trasformando il fail pulito in SIGSEGV (verificato). Serve
  rendere dinamici/coerenti tutti i cap insieme — vedi «Lavori grossi
  futuri §1». Pattern raro (forward+run normale OK a qualsiasi N).
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
ritorna set di fn dove ha sparato un cond-hoist **self-mut dentro un loop**
(`for/while { if(E legge X) ... scrive X }`). Queste fn escluse da
`apply_uncall_opt` / `apply_void_uncall_opt`. Ristretto 2026-05-31: il
sotto-caso TernaryOp-in-cond-hoisted NON è più escluso (il bug era il
dispatch nested-IF della VM, Kairos 5098d1f, ora risolto;
`generic_if_ternary_index.c` passa opt-uncall). Verificato: sweep
base-vs-opt su tutte le 163 generic = 163 MATCH con l'esclusione ristretta.
Resta escluso solo il self-mut (es. `touch_idx_loop` in
`generic_if_arr_self_mut.c`): sotto opt-uncall dà ancora `DELOCAL
__mn_lc1 atteso=0 trovato=1` (loop-counter, vedi sotto).

**opt-uncall: loop con IF body data-variante (P3 branch_trace replay)**.
Ultima esclusione `loop_hoist_targets`. Pattern: fn con
`for/while { if(E) BODY }` SOTTO `--opt-uncall-user-calls`, es.
`touch_idx_loop` in `generic_if_arr_self_mut.c`. Fallisce
`DELOCAL frame=touch_idx_loop var=__mn_lc1 atteso=0 trovato=1`.

**Diagnosi precisa (2026-05-31, NON è loop-counter né contamination)**:
data-dependent. Il fallimento avviene SOLO quando la decisione dell'IF nel
body **varia tra iterazioni**:
- loop con tutte le iterazioni che prendono lo stesso ramo (es. G tutti 0,
  `if(G[i]==0)` sempre true) → INVERTE ok;
- una iterazione diversa (es. `G[0]=5` → i=0 false, i=1/2 true), o tutte
  false → DELOCAL lc1.
Lo si espone facilmente perché basta una opt-uncall'd fn PRIMA che scriva
memoria (es. `bump(){G[0]+=5}`): il suo XOR-swap lascia G[0]=5, quindi
`touch_idx_loop` vede l'IF variabile. Un prologo che NON tocca memoria
(fn vuota) non rompe.

**Root**: il meccanismo "Fix P3" branch_trace (Janus.c op_jmpf push +
vm_invert.h JMPF_ELSE replay). Forward, dentro il pattern opt-uncall,
`op_jmpf` registra ogni decisione IF in `vm->branch_trace` (in ordine di
esecuzione). L'inverse legge la finestra `[trace_window_start, top)` in
**FIFO** (`trace_idx = win_start + cursor++`). Per decisioni uniformi
funziona; quando variano tra iterazioni il replay associa la decisione
SBAGLIATA a una iterazione → ramo invertito errato → hist pop sbilanciato
→ `e0` (loop-guard) non ripristinato → `lc1 -= 0` invece di `lc1 -= 1`.
Verificato con dump trace reads (h2 all-true: idx 0→13 ok; h1 mixed:
fallisce a idx12). Tentativo di consumo LIFO (leggere dalla cima)
ROMPE il caso uniforme → l'ordine corretto non è il semplice reverse:
il from-loop inverse + peel interagisce col cursor in modo non banale.
Serve capire l'ordine di encounter degli IF nell'inverse del from-loop
(peel) per mappare correttamente il cursor alle iterazioni. Path
condiviso encrypt/DES → validare ampio, NON blind. Quando risolto:
rimuovere l'esclusione `loop_hoist_targets` (compile.py) → opt-uncall
completo su loop con IF body.

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

**Frame fields statici — bumpati (FATTO)**: valori correnti in
`vm_types.h` già oltre i vecchi target: `MAX_VARS=4096`, `MAX_LABEL=16384`,
`MAX_NESTED=4096`, `MAX_PROC_PARAMS=1024`, `VM_TRACE_WIN_STACK_MAX=4096`,
`IF_BRANCH_STACK_MAX=65536`. `kairos_limits.py` allineato
(`KAIROS_MAX_PROC_PARAMS=1000 ≤ 1024`). Resta come future-proof la dyn
alloc per-Frame (realloc inline) al posto del bump statico, ma non urgente.

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
