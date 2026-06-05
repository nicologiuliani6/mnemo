# TODO

## Stato

Nessun gap funzionale aperto. Mnemo è **1:1 con gcc** sull'intero subset C
reversibile, verificato a corpus (`c_probe/`: 155/155 byte-byte, 0 mismatch) +
gate (`make test-gcc-compat` 189/189, pytest 25/25, encrypt/des invertibili).
Coperto: puntatori (multi-livello, aritmetica, callback/fn-ptr-param,
row-pointer `int(*r)[N]`, doppia-indirezione), strutture (annidate,
array-di-struct + `a[i].field` su puntatore, union/union-in-struct, copia,
ritorno, campo-array annidato `g.rows[i].cells[j]`), passaggio (valore/ptr/
array/struct, ricorsione), aritmetica interi (unsigned wrap mod 2^32, shift
signed aritmetico), stringhe char*/char[] (riassegnazione, return, `printf("%s",
f())`), control flow completo (switch+return, fn-ptr array a indice runtime).

Restano solo le divergenze qui sotto + ottimizzazioni di performance.

## Limiti noti (trovati a corpus, fix non banale)

- **`printf("%s", buf)` con `buf` puntatore a buffer su HEAP** (`malloc`):
  il dispatch `%s` matcha solo stringhe statiche note (ROS/char[]); per un
  buffer heap servirebbe un loop reversibile che legge `pool[buf+i]` fino al
  NUL e fa show. Le stringhe statiche/letterali e `char[]` locali funzionano.
  (repro `c_probe/t/p6_string_dup.c`).
- **`realloc` manuale in loop** (`malloc` nuovo + copia + `free` + riassegna il
  puntatore, dentro un ciclo): semantica re-alloc difficile da invertire (vedi
  anche `realloc` in "Non fattibile"). Il caso fuori-loop funziona.
  (repro `c_probe/t/p6_dyn_grow.c`).
- **fn-ptr come CAMPO di struct** (`struct{int(*f)(int,int);}; ops[i].f(3,4)`):
  il binding fn-ptr a indice/campo struct non è risolto (scalar fn-ptr var,
  array di fn-ptr e fn-ptr param funzionano; il campo struct no). Serve
  estendere `_resolve_indirect_callee` al caso `StructRef.f(...)` + dispatch su
  tag in cella `s__field`. (repro `c_probe/t/p8_fnptr_in_struct.c`).
- **union type-punning int↔byte** (`union{int i;unsigned char b[4];}; u.i=…;
  u.b[k]`): il word-model (1 cella = 1 word a 4 byte) non aliasa i sotto-byte;
  scrivere `u.i` non popola `u.b[]`. Union "tagged" (un membro alla volta dello
  stesso width) funziona; il reinterpret byte-wise no. (repro
  `c_probe/t/p8_union.c`).

## Opt-uncall + u64-shift / opt-uncall su loop interni — RISOLTO

Entrambi i bug che bloccavano `--opt-uncall-user-calls` sulle fn con `uint64_t` +
shift (e in generale sulle fn con loop interno) sono RISOLTI lato Kairos VM. Il
seed `_function_uses_u64_shift` è stato rimosso: opt si applica ora a des
(permute/feistel). Riduzione celle confermata (caso u64+loop: cells_final
1010445→164, cells_max 6.07M→317K). Snapshot ristretto al write-set
(`_compute_callee_mem_writes`): copre solo le celle che il callee MODIFICA, non
quelle solo lette (per `permute` erano 917/918).

**NB perf — perché des-opt è ~8x (non il ~2.3x atteso).** Diagnosi a contatori
(VM heartbeat su forward-loop, invert-loop, push/pop, go_to_line):
`des-opt ≈ 2x × ~4x`.
- **2x** = l'opt esegue `call f` + `uncall f` (l'uncall ripete l'inverse del
  corpo). Atteso e accettabile.
- **~4x per-op** = des legge le tabelle con `tbl[i]` → `call __mn_pool_load`, una
  procedura con **917 PARAM** (una cella nominata per parametro, servono tutte al
  dispatch binary-search `if slot<mid …`). Ogni lettura di tabella lega 917
  parametri; `permute` fa ~64 letture, chiamata ~16 volte. L'opt RADDOPPIA tutte
  queste call pesanti (forward + uncall) e l'inversione aggiunge overhead per-op.
  Il forward-loop gira a ~8k op/s (vs ~33k baseline). NON è un O(n²) singolo né
  lo snapshot (già ristretto a write-set 917→3) né `go_to_line`: è il volume di
  PARAM-binding di `__mn_pool_load` × raddoppio opt × overhead inverse.

**AGGIORNAMENTO**: il PARAM-binding di `__mn_pool_load` è stato eliminato con la
**native interception** (kairos `df89c03`, vedi "Ottimizzazioni future"): la VM
esegue `out=mem[slot]` in C senza legare i 917 param. des **baseline 2m23s →
~1m32s**. Questo dimezza anche des-opt (~8x → ~4x). Il collo RESIDUO dell'opt è
ora il replay-uncall del **bitwise di feistel** (native and/or hist O(31×31)/op,
16 round, raddoppiato), inerente all'opt su codice bitwise-heavy.

Conclusione: l'opt è CORRETTO e riduce le celle. Su des conviene comunque NON
attivarlo (bitwise-heavy → net loss in tempo); `--auto` lo riconosce e attiva
solo `--native-arith`. Su fn con corpo economico l'opt è vantaggioso.

**Bug #1 — POP stack vuoto: RISOLTO** (ipotesi "Kairos uncall rotto" confermata).
La causa NON era il floor-snap né lo shift-into: era il native hist undo a 64-bit.
`mn_floor_div2_signed_hist_undo` (in kairos `mn_native_arith.h`) decideva il ramo
`>=0`/`<0` dal valore `ts` POPPATO dalla hist invece che dal valore LIVE usato dal
replay. Su operandi int64 NEGATIVI (high bit set, es. `x>>(64-n)`) il segno
poppato divergeva da quello live → push/pop count mismatch nel native `and/or`
hist (`mn_and_or_hist_*` via `mn_bit_k_signed_*`) → cascata → `[VM] POP: stack
vuoto! (frame=__mn_shr_into … inv=3)`. Diagnosi: contatori `floor_div2 replay=930
neg=465 vs undo neg=225`. Fix: undo ora **live-value-driven** (riceve `t_in`/`tb` e
sceglie il ramo dal segno live, come il replay), in `mn_floor_div2_signed_hist_undo`
+ caller (`mn_bit_k_signed_hist_undo` usa il `t` ricomputato, `mn_shr_into_hist_undo`,
`mn_floor_div2_signed_native_inv` passa `*q` come proxy di segno). Verificato:
rotate/u64shift opt+native byte-1:1 (regression guard `c_test/inv_u64_rot_opt.c`),
encrypt opt+native+check-invertibility non regredito, gcc-compat 189/189.

**Bug #2 — DELOCAL loop-counter sotto opt-uncall: RISOLTO** (era pre-esistente e
NON u64-specifico). Causa: la forward `op_jmpf` pushava su `branch_trace` una
entry per OGNI IF, inclusi quelli DENTRO un from-loop, ma l'inverse di quegli IF
usa il recompute (`line_inside_loop_body`) e non consuma il cursor della window →
window LIFO disallineata → gli IF top-level leggevano branch errati → push orfana
→ `[VM] DELOCAL: __mn_lc1 atteso=0 trovato=1`. Repro INT `/tmp/loopopt.c`
(`int acc(int n){int s=0;for(i<n)s+=i;return s;}`). Fix Kairos
(`Janus.c`/`vm_ops.h`/`vm_types.h`): al window-activation si cachano le line-range
dei from-loop del callee (`collect_loops` → `bt_loop_lo/hi`); `op_jmpf` non pusha
gli IF dentro quelle range → window allineata. Verificato: loop-opt
(sum/runtime/fixed), nested loop+IF, nested u64+shift tutti byte-1:1; encrypt
opt+native+check-inv invariato; gcc-compat 189/189.

## Ottimizzazioni future (performance, non correttezza)

Il collo di bottiglia era l'**indicizzazione array a indice RUNTIME** via
puntatore (`tbl[i]` con `tbl` puntatore-param e `i` variabile): lowerata come
deref pool `__mn_pool_load(slot, …)`, con dispatch slot→cella.

- ✅ **FATTO — dispatch binary-search** (`if slot < mid then … else …`,
  O(log N) invece di O(N) lineare). `custom_lib/des.c` (DES completo) ora gira
  in ~141s con `--native-arith`, output byte-1:1 con gcc
  (`CT=85E813540F0AB405`, round-trip ok); `permute(IP)` da >200s a 0.65s.
  L'accesso DIRETTO `a[i]` su array noto era già disj-chain O(N_array).

- ✅ **FATTO — native interception di `__mn_pool_load`** (kairos `df89c03`). Il
  vero collo NON era il dispatch (già O(log N)) ma il **binding dei ~917
  parametri** del `call __mn_pool_load(slot, __mn_mem0..N, out, …)` a ogni
  `tbl[i]`. Sotto `--native-arith` la VM intercetta `call`/uncall di pool_load ed
  esegue `out=mem[slot]` in C sul frame chiamante, con gli STESSI 2 push su
  `__mn_hist` del bytecode (forward+inverse interscambiabili, niente nuovo
  opcode). **des baseline 2m23s → ~1m32s (~35%)**, 1:1 verificato (CT, corpus
  native-arith, table-read opt+check-invertibility). Solo LOAD (read-only,
  reversibilità banale); store/dyn invariati.

- ✅ **FATTO — `mnemo run --auto`** (mnemo `5191d16`): sceglie native_arith /
  opt_uncall dal contenuto del `.c` (conteggio arith/bitwise/arrayref + celle
  statiche). `auto_select_optimizations` in compile.py. Es. des → native_arith
  (1m30s), opt_uncall=False (bitwise-heavy); big-array light → opt_uncall.

Idee ulteriori (se servisse altra velocità):

1. **des-opt resta lento** anche col pool_load nativo (~4x, era ~8x). Collo
   residuo: il replay-uncall del **bitwise di feistel** (native `mn_and_or_hist_*`
   O(31×31)/op × 16 round, raddoppiato dall'opt). Inerente all'opt su codice
   bitwise-heavy → `--auto` correttamente NON attiva opt su des. Per ridurlo
   servirebbe un native and/or hist più compatto, o non opt-are le fn bitwise.
2. **Op VM nativa MEMGET/MEMSET** con NUOVO opcode: scartata (bytecode congelato).
   L'interception di pool_load (sopra) copre il caso senza toccare l'ISA.

## Divergenze per design / comportamento non-definito (non bug)

- **`int` è 64-bit**: l'overflow `int` signed (UB in C) non wrappa a 32-bit.
  L'`unsigned` invece wrappa correttamente mod 2^32.
- **`sizeof(T*)` = 4** (modello a word: puntatore = 1 cella).
- **Ordine di valutazione degli argomenti** L-to-R (gcc x86-64 R-to-L) —
  unspecified in C; rileva solo con argomenti che hanno side-effect.

## Bounded-by-design (non bug)

- **`STACK_MAX=4096`** (`stack.h`, lo `Stack` di `Var*` usato da
  `LocalVariables`): profondità di `local` per-Frame. Irraggiungibile via Mnemo
  (il layout cap­pa le celle a 2048 < 4096). Convertirlo a dinamico romperebbe la
  copia by-value dello `Stack` (inline) usata nel save/restore di
  CALL/UNCALL/par/inversione (~10 siti + `CallRecord.saved_local_vars`) → rischio
  alto sul core fragile per zero guadagno raggiungibile. Si tiene statico. NB: la
  crescita dinamica di `Frame.vars` (oltre 4096) È verificata di per sé — un
  `.kairos` scritto a mano con 5000 `local` somma corretto una volta alzato
  `STACK_MAX`; è solo lo `Stack` a fare da tappo prima.
- **`IF_BRANCH_STACK_MAX=65536`** (thread-local, `vm_ops.h`): stack di profondità
  IF per thread. 65536 IF annidati in un singolo path di esecuzione è
  irraggiungibile; la versione thread-local dinamica leakerebbe a thread-exit →
  si tiene statico, stesso criterio dei `DBG_MAX_*`.
- **`DBG_MAX_BREAKPOINTS=256`, `DBG_MAX_HISTORY=4096`**: limiti del debugger DAP
  (history = ring-buffer). Solo debug interattivo.

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
