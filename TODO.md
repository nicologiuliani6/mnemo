# TODO

## Bug aperti (verificati, fix rischioso/non banale)

- **Semantica tipi interi: Mnemo è internamente all-signed-int.** Non modella le
  *usual arithmetic conversions* del C. Due manifestazioni:
  - **`char`/`unsigned char` non wrappa a 8 bit**: `unsigned char c=250; c+=10;`
    dà 260 invece di 4. Fix = tipo char a 8 bit (mask 0xFF su TUTTI i path di
    scrittura `=`/`+=`/`++`/subscript + char signed-default x86). Repro
    `c_test/bug_uchar_wrap.c`.
  - **Confronti misti signed/unsigned**: `unsigned a=10; int b=-20; (a+b)<0` →
    gcc "pos" (la somma è unsigned, mai <0), Mnemo "neg" (confronto signed). Il
    *valore* è giusto (stessi bit, %u/%d corretti); è il confronto `<`/`>` che
    usa la signedness sbagliata. Repro `c_test/bug_mixed_sign_cmp.c`.
  Fix comune = tracciare la signedness/width attraverso le espressioni ed
  emettere op (confronto, mask) coerenti → invasivo (type-system), alto rischio
  su string-ops (22 test usano char) e su encrypt/des (unsigned-heavy).

## Ottimizzazioni mancanti

- **`--opt-uncall-user-calls` non ottimizza la memoria nei cicli con malloc.**
  Su `c_test/malloc_test.c` (100 `malloc` in loop, solo l'ultimo `p` vivo) le
  stats VM sono IDENTICHE con e senza il flag:
  `cells_final 1452 / cells_mean 1362.61 / cells_max 5084` in entrambi i casi.
  L'opt agisce solo su snapshot/uncall delle celle `__mn_mem*` nominate, NON
  sulle allocazioni dell'heap dinamico (`vm->mn_pool`): le 99 allocazioni morte
  del loop restano nel pool. Idea: riconoscere gli slot pool non più
  raggiungibili (es. malloc senza free il cui puntatore è sovrascritto a ogni
  iterazione) e ridurli/riusarli — difficile in modello reversibile (il
  ripristino inverso richiede la storia delle allocazioni), valutare un
  free-implicito reversibile o riuso dello slot a parità di `nblk`.

## Migliorie / limiti noti (non bloccanti)

- **Bitwise in interprete puro O(value) sugli operandi grandi**: `2147483647|1`
  in interprete è lentissimo/hang (le halving reversibili sono O(value)). Usare
  `--native-arith` (bypassa `lib/bits.kairos`, C O(1)). Perf pre-esistente, non
  correttezza.
- **`struct P *p = arr` (puntatore a base array-di-struct)** non supportato
  (`identificatore non dichiarato` sul nome array, probe `s10`). L'init
  dell'array-di-struct invece ora funziona.
- **Indicizzazione su non-nome**: `2[a]` (== `a[2]`, probe `r17`) e
  `"ABCDE"[i]` (indice runtime su letterale stringa, probe `u12`) non
  supportati: `array: la base dell'indicizzazione deve essere un nome`. Il caso
  letterale a indice costante è compile-time-foldabile; quello runtime serve un
  buffer materializzato. Sintassi rara.
- **Campo union/struct annidato `u.s.a`** non supportato: `union: un solo
  livello di campo` (probe `v03`).
- **`char *n; n = "literal";` (riassegnazione da letterale) + `printf("%s",n)`**
  non supportato in alcuni contesti (es. dentro `switch`): `letterale stringa
  non è un valore intero` (probe `v12`). L'init diretto `char *p="..."` invece
  funziona.
- **Ricorsione mista self+mutua: possibile collisione di frame-key.** Il clone
  per la mutua usa `Frame.active` come depth, la self-rec usa il parsing `@N`
  del frame name (Janus.c). Una proc raggiunta SIA da self- SIA da mutua-
  ricorsione nello stesso path potrebbe generare chiavi `proc@depth`
  collidenti. Caso limite non coperto dai test (mutua a 2/3 vie + self pure
  OK). Verificare/serve uno schema di depth unificato se emerge.
- **`_Generic` non distingue `char` da `int`.** Mnemo aliasa `char` a `int`
  nel type-system → `_Generic((c), char:…, int:…)` sceglie sempre `int`.
  Probe `p22`. Richiede un tag di tipo `char` separato nel lowering.
- **Array di puntatori a funzione non supportati** (`int (*ops[2])(int)`).
  Probe `p07` → `array: elemento supportato solo se scalare/puntatore`.
  Solo fnptr scalari compile-time-resolved oggi.

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
