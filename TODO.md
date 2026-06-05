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

## Opt-uncall + u64-shift: POP stack vuoto (da investigare)

`--opt-uncall-user-calls` su funzioni con `uint64_t` + shift (`<<`/`>>`) è
**escluso** (euristica `_function_uses_u64_shift` → seed in
`uncall_extra_seeds`). Per questo su `custom_lib/des.c` l'opt non riduce le
celle: tutte le des fn (e `main`, transitivamente) sono nel set escluso. Causa
concreta verificata (`/tmp/u64shift.c`, `des.c`): lo shift variabile u64 lowera
ai lib proc `__mn_shl_into`/`__mn_shr_into`, che PUSHano su `__mn_hist`; l'opt
fa `__mn_hist_floor_snap` + `uncall`, l'inverse del proc pop `__mn_hist` ma il
floor-snap ha già spostato il floor → `[VM] POP: stack vuoto!
(frame=__mn_shr_into … inv=3)`. Senza il seed l'output è vuoto/crash.

Per togliere l'esclusione (e far ottimizzare des) serve capire QUALE dei 3 lati
sbaglia:
1. **Mnemo emette male** — `__mn_hist_floor_snap`/snapshot non considera che il
   callee ha già pushato su `__mn_hist` per gli shift-into; il floor andrebbe
   calcolato DOPO quei push, o gli shift-into non dovrebbero toccare `__mn_hist`.
2. **Kairos `uncall` rotto** — l'inverse di `call f` con shift-into non
   ripristina il floor di `__mn_hist` correttamente.
3. **Kairos manca un controllo statico** — un `.kairos` che perde informazione
   (pop oltre il floor in inverse) dovrebbe essere RIFIUTATO a compile/load time
   dal frontend Kairos, non crashare a runtime con POP vuoto. Oggi nessun check
   statico di bilanciamento stack cross-call/uncall.

Finché non risolto, l'esclusione è la scelta corretta (correttezza > perf).

## Ottimizzazioni future (performance, non correttezza)

Il collo di bottiglia era l'**indicizzazione array a indice RUNTIME** via
puntatore (`tbl[i]` con `tbl` puntatore-param e `i` variabile): lowerata come
deref pool `__mn_pool_load(slot, …)`, con dispatch slot→cella.

- ✅ **FATTO — dispatch binary-search** (`if slot < mid then … else …`,
  O(log N) invece di O(N) lineare). `custom_lib/des.c` (DES completo) ora gira
  in ~141s con `--native-arith`, output byte-1:1 con gcc
  (`CT=85E813540F0AB405`, round-trip ok); `permute(IP)` da >200s a 0.65s.
  L'accesso DIRETTO `a[i]` su array noto era già disj-chain O(N_array).

Idee ulteriori (se servisse altra velocità):

1. **Op VM nativa di accesso indicizzato** (`MEMGET/MEMSET` su `__mn_mem`):
   read/write diretto O(1) sull'array delle celle nominate (come `POOLGET` ma
   sui named-cell). Risolve alla radice; tocca VM + lowering + reversibilità.
2. **Native-arith per `&`/`|`/`<<`** anche fuori da `--native-arith`, o
   riduzione delle iterazioni bitwise (oggi 31 iter/op nel path interpretato).

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
