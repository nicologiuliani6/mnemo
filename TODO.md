# TODO

## OPEN

### [P2] PC.c par-uncall correctness — PARTIAL FIX 2026-05-20

Gate aggiunto: `par_uncall_eligible` ora esclude worker se in
`channel_using_targets`. PC.c con `--opt-uncall-user-calls` ora exit=0
(prima exit=1 con `[VM] MINEQ: variabile '__mn_lc0' è NULL` durante
par-uncall inverse). Test aggiornato (`test_par_uncall_channels.py`)
per asserire che producer/consumer non ricevano par-uncall.

**Bug VM sottostante**: par-uncall lancia 2 thread `is_inverse=0` che
eseguono `uncall producer`/`uncall consumer` concorrentemente. Ogni
thread chiama `invert_op_to_line` su frame clonato (`producer@tXXX`).
Loop counter `__mn_lc0` viene riportato NULL durante MINEQ. Probabile:
- `op_local` per `__mn_lc0` (inverse DELOCAL) non eseguito sul clone
  frame perché qualche path skippa l'init.
- Oppure stesso pattern di `recursion senza parallel2`: clone frame
  aliasing fa sì che la Var* lc0 venga liberata da un altro thread.

Tentativo `__thread` su `_fa_cache`: non risolve. Cache disabilita
diversamente: `DELOCAL valore finale errato lc1=9 atteso=0` — bug
diverso, probabilmente loop body inversion mancante.

Per ripristinare par-uncall su channel workers serve fix VM:
1. Verificare semantica `clone_frame_for_thread` per locali (LOCAL
   stack preservato?).
2. Trace su quale thread vede `__mn_lc0=NULL`: producer thread può
   essere bloccato da consumer thread che reclama lo slot?
3. Possibilmente, sequenzializza par-uncall per channel workers
   (snap → call f0; call f1; ... → uncall f0; uncall f1 sequenziale).
   Questo manterrebbe symmetric channel inverse senza race su frame.

Tempo stimato: 4-8 ore + design review.

### [P3] VM optimization: encrypt 5.4x → 2.30x — DONE 2026-05-19

Cleanup hot path in `vm_invert.h`:

1. **Debug log gating**: 8 `// #region agent log` blocks (fopen+fwrite+fclose per invocation) → gated by `MNEMO_AGENT_LOG`. Encrypt sys time 15s → 1s.
2. **strdup elimination**: `invert_op_to_line` non più strdup(buffer) — buffer è già thread-locale (vm_par.h dup_buffer); mutations transienti (`*newline='\0'` poi restore).
3. **Arena allocation**: per-invert one malloc instead of N strdups per line. `lp[]` punta nell'arena, single free.
4. **Opcode int dispatch**: nuovo `enum InvOpTag`, `classify_op()` (line 75 vm_invert.h), `lp_op[]` array precompute al collection. Inner loop dispatch via switch.
5. **Per-frame analysis cache** (`_fa_cache[64]`): collect_loops/ifs/par_ranges results cached per base frame name. ~50KB scan evitato.
6. **strstr cache**: `_is_divmod_nonneg`/`_is_bit_k_signed` computed once outside hot loop.
7. **line_loop/if_zone fast path**: per ops non-JMPF/LABEL/JMP, skip strcmp-based variant.
8. **char_id_map first-char filter + lookup combine**: VarIndexer lookups (chiamati in ogni op handler) ora hanno first-char prefix check; `char_id_map_lookup` ritorna -1 per miss invece di richiedere doppia scansione `exists+get`.

Encrypt timing:
- baseline 7.9s
- --opt-uncall-user-calls 18s (era 47s pre-opt)
- ratio 2.30x (era 5.4x).

Test regression: 36 mnemo + 14 unit + 71 gcc-compat = 121 PASS.

### [P3] opt A+B: snap subset + procedure sig reduction — DONE 2026-05-19

**A** (snap subset): `--opt-uncall-user-calls` ora snappa solo le celle in `callee_mem_touches[name]` invece di tutte `__mn_mem*`. Applicato sia in `_lower_funccall_with_ret` (call singola) sia in parallel2 par-uncall. Stack history molto più corta.

**B** (sig reduction): ogni `procedure f(...)` ora dichiara formali `int __mn_mem<i>` solo per `i in callee_mem_touches[f]`. Tutti i call site (call/uncall singole, parallel2, parallel_with, parallel_with1, pthread_start, pthread_start1) passano lo stesso sottoinsieme. Probe pass sempre eseguito (anche senza `--opt-uncall-user-calls`).

Implementazione:
- `_compute_callee_mem_touches`: punto-fisso, callee-frame indices [0..S-1].
- `_collect_mem_refs_from_seq`: `ICall`/`IUncall` args NON contati come direct refs (solo `(proc, args)` per propagazione fixpoint).
- `_parallel_branch_mem_actuals(left, callee_name)`: actuals = sorted touches mappate caller-side (base=0 per left, S per right, shared se in `parallel_file_shared_slots`).
- `_lower_user_function`: `param_order = sorted(callee_mem_touches[name])` (fallback range(total_cells) se entry mancante).

Esempio fib.c (S=10):
- `procedure fibonacci(int __mn_mem4, int __mn_mem5, ...)` (era 10 celle).
- `procedure fib_left(int __mn_mem0, int __mn_mem2, int __mn_mem4, int __mn_mem5, ...)` (4 celle invece di 10).

Validato: make test 36/36 PASS, test-unit 6/6 OK, test-gcc-compat 68/68 PASS, fib.c opt-uncall → 89, ex33 opt-uncall → 55. Tests parallel partition aggiornati (sottoinsiemi possono differire tra workers, invariante è offset partizione applicato).

### [P3] opt-uncall su `par … and … rap` — DONE 2026-05-18

`mnemo_pthread_parallel2(f0, f1, …)` con `--opt-uncall-user-calls` ora emette:
```
[snap mem 2·S → __mn_e<N>] (forward par mutates mem)
par
  call f0(...)
and
  call f1(...)
rap
__mn_e<N> ^= __mn_mem<k>  (per ogni cella → e = post-par)
par
  uncall f0(...)
and
  uncall f1(...)
rap
[3-XOR swap mem<->e]  (mem = post-par result, e = pre-par)
```

Vincolo necessario: body dei worker NON deve usare opt-uncall interno (altrimenti nested call/uncall pattern fa DELOCAL fail su `__mn_e<N> != 0`). Implementato via:
- `infer_par2_workers_all(ast)`: raccoglie entrambi gli arg0/arg1 di tutte le `parallel2`
- `_Ctx.par2_workers`: set propagato a lowering di ogni user fn
- gate `not in_par2_worker` su `apply_uncall_opt`/`apply_void_uncall_opt`

Validato: fib.c → 89 (era 89 baseline), ex33 → 55 (baseline 55), ex30/31/32/34 invariati.

### [P3] opt-uncall self-recursion (fibonacci → fibonacci) — DEFERRED

**Stato 2026-05-18**: `self_rec` guard re-installato in c_lower.py (apply_uncall_opt/apply_void_uncall_opt entrambi `and not self_rec`). Forward call + uncall caller-side ancora attivi (gestiti da opt-uncall normale per callee non-self). `make test` 36 PASS, `make test-unit` 6 OK, `make test-gcc-compat` 68/68 PASS. fib.c con `--opt-uncall-user-calls` torna 89 corretto.

**Fix VM richiesto per rimuovere il guard**: vedi analisi storica sotto. Sintesi: pass inverse profondo (inv>=15) su clone DELOCALato forward (fi=22, 23 nei probe) non ri-LOCALizza `__mn_e<N>` via DELOCAL→op_local mapping. Trace [LOC12] non scatta in inverse anche se [XOR12] sì → percorso esecutivo bypassa invert_op_to_line entry per quei frame. Probabile interazione exec_par_threads + clone_frame_for_depth.

### [P3-archived] Analisi storica

**Errore corrente** (rimuovendo `self_rec`): `XOREQ __mn_e12 NULL frame=fibonacci@w<tid>_N`. Si manifesta in fib.c con PAR (fib_left/fib_right entrambi recurono).

**Progress**:
- ✅ VM `exec_branch_inverse` CALL handler ora gestisce caso ricorsivo (clone_frame_for_depth + invert_op_to_line) — kairos 0166749.
- ✅ `init_clone_frame` duplica slot INT DECL per opt-uncall su recursive — kairos be9da45.
- ❌ Sub-issue identificato: `Janus.c` UNCALL handler usa `char_id_map_get(&FrameIndexer, pn)` (base frame) anziché clone per il depth corrente. Fix abbozzato (detect self-rec via `pn == base_of_fname`, computa `new_dep = caller_dep + 1`, `clone_frame_for_depth(pn, new_dep)`, `inv_name = make_frame_key{,_par_rec}`) compila ma non risolve l'errore — `__mn_e12` resta NULL nel caller depth-7.
- ❓ Probabile causa restante: `base_var_count = param_count = 12` (LOCAL non eseguito sul base frame → `var_count` non bumped). `exec_branch_inverse` allocazione tmp slots itera `[0, var_count)`, quindi __mn_e<idx=24> non viene ri-allocato quando manca. Cross-thread (fib_left vs fib_right) genera tid distinti nelle par_rec keys → cache mismatch indipendente.

**Analisi successiva (sessione 2026-05-18)**:
- `var_count` base = 12 (solo PARAM/DECL) come da trace. Però `op_local` su clone bumpa `var_count` clone-side a 38 (12 + 26 __mn_e<N>). Quindi `exec_branch_inverse` iterando `[0, var_count)` SU CLONE dovrebbe coprire idx=24. Hypothesis "var_count blocca alloc tmp" smentita.
- `delete_var` (`vm_helpers.h:230`) **non decrementa** size — var_count cresce monotono. DELOCAL non causa shrink.
- `op_local` (`vm_ops.h:929`) sempre re-alloca slot anche se non-NULL. Quindi LOCAL forward forza allocazione fresca su clone reuse.
- Setup `pthread_self`-based par_rec key: ogni thread ha tid distinto → fib_left/fib_right hanno cache di clone disgiunte; nessun race su FrameIndexer.

**Trace verificato (sessione 2026-05-18, run su fib.c PAR)**:
- `LOCAL` (forward) GIRA per __mn_e12 su tutti i clone (fi=7..23 incluse fibonacci@wf1e426c0_7 fi=22, fibonacci@wf2a786c0_8 fi=23).
- `XOREQ` (forward inv=0) GIRA fi=20 con vars[24] valido.
- `XOREQ` (inverse inv=1..15) GIRA su fi=21,7,8,9,10,...,20,19 con vars[24] valido.
- Ultimo `XOREQ` (inverse inv=15) su fi=22 (fibonacci@wf1e426c0_7) **trova vars[24]=nil** → panic.
- inv=15 implica 15 nesting di UNCALL/CALL inversi (ricorsione profonda + opt-uncall).

**Conclusione**: forward + DELOCAL girano correttamente. Ma DURANTE inverse-stack profondo, `vars[24]` di fi=22 viene **liberato** da un path intermedio. Forse:
1. END_PROC fi=22 (forward) ha azzerato vars[24] via DELOCAL — la successiva re-entry in fi=22 via UNCALL handler dovrebbe re-LOCAL ma non lo fa per certi cammini (es. se UNCALL passa direttamente a invert_op_to_line saltando il setup di LOCAL).
2. O: `delete_var` chiamato da op_local stesso (line 929-930) prima di re-allocare, ma in mezzo qualche path lascia vars[24] nil.

**Prossimo step necessario** (architectural, non semplice patch):
- Capire perché fi=22 entra in pass inverse senza prima ri-eseguire LOCAL `__mn_e<N>`. Verosimilmente è `exec_branch_inverse` chiamato da UNCALL nesting che opera su sub-range del body (skip proc-level LOCAL/DELOCAL ops).
- Allocare slot `tmp_alloc` in `exec_branch_inverse` se NULL ma idx < var_count. Già fatto (vm_invert.h:1218-1226) ma forse non scatta per il caso. Verificare.

**Quarto probe (sessione 2026-05-18, "FALLO")**: tre fix applicati in combinazione:
1. `Janus.c` vm_exec: pre-registra `LOCAL` vars nell'VarIndexer base (rimuove "non definita" su __mn_e<N>).
2. `Janus.c` UNCALL handler: detect self-rec + `clone_frame_for_depth` (allinea callee con CALL).
3. `vm_invert.h` invert_op_to_line: tmp_alloc INT slot mancanti per `fi != fi_reset`.

Risultati:
- fib(1) (no recursion): OK.
- fib(2), sumto, fib(10) PAR: SIGSEGV.

Probabile: tmp_alloc race con frame_top tracking, o conflitto con op_local re-allocation che fa `delete_var` su slot ancora referenziati altrove.

Conclusione: ogni layer di fix sblocca un layer più profondo di crash. Fix richiede:
- Verifica end-to-end del flusso UNCALL nesting (track quale fi è target di ogni invert_op_to_line nested e quali Var* sono shared).
- Possibilmente revisitare semantica delete_var (non decrementa size — slot orfani indefiniti).
- Considerare se opt-uncall pattern emit Mnemo è semanticamente compatibile con self-rec o servirebbe un emit alternativo (es. inline manuale del callee body).

Tempo stimato residuo: 6-10 ore + design review. Tutti probe reverted, baseline 36+6+68 green.

---

## DONE (recente)

- ✅ P3 0-iter loop: counter-loop wrappato in `IIfKairos g != 0` (g=snapshot init_lc, ILocalBlock con fresh_loop_ct). VM: aggiunto `line_is_inside_if_subrange` + thread-local globals `g_invert_nested_filter_from/to` settati da `exec_branch_inverse` FROM-loop fallback → `invert_op_to_line(honor=0)` skippa righe interne ai nested IF nel sub-range. `for(i=0;i<0;i++)` ora exit gcc-matching. Reg 36+6+68 green.
- ✅ P4 cleanup `loop_mnemo_deep_increment`: rimossi `loop_body_use_deep_peel`, `loop_mnemo_deep_increment`, `loop_body_has_nested_if`, `loop_body_has_call_or_uncall`, `loop_body_push_count_to_stack`, array `jmp_start_deep[MAX_LOOPS]` e tutti i call site. Reg 36+6+68 green.

- ✅ ex21 check-invertibility: `exec_branch_inverse` nested-IF dispatch (vm_invert.h) — branch con nested IF usa collect_ifs + iter reverse con skip lines dei nested + dispatch JMPF_ELSE → recurse su ramo forward. Reg passa 36 mnemo + 6 unit + 68 gcc-compat.
- ✅ fib real-par (top-level PAR + sequential recursion, `c_test/fib.c`)
- ✅ srecv mailbox-accumulation fix (`mnemo c_lower.py` srecv `-= 1` post-pthread_mutex_lock/destroy)
- ✅ counter-based loop lowering (`_build_counter_loop_instrs` in c_lower.py) → check-invertibility passa su loop body non-vuoto (ex18/ex19/sum)
- ✅ collect_ifs nested IFs uid-matched stack (vm_invert.h)
- ✅ opt-uncall su callee ricorsivo non-self (`not self_rec` invece di `not rec`) → fib_left/fib_right wrap fibonacci con call+uncall
- ✅ init_clone_frame duplica int DECL slots per opt-uncall su recursive

---

## C standard — features non implementate

Mnemo compila un sottoinsieme reversibile di C. Per riferimento completo: `.cursor/rules/mnemo-c-subset.mdc` e `README.md` §"Mnemo rispetto al C standard". Lista delle features C ancora non supportate, ordinate per impatto/difficoltà:

### Tipi scalari mancanti

- ~~**`char` come variabile**~~ — ora supportato (`char c = 'A'; char d = c+1;` funziona).
- ~~**`short`, `long`, `long long`, `unsigned short/long/long long`**~~ — già accettati come scalari (alias `int` via VM word-size).
- **`float`, `double`, `long double`** — nessun FP. La VM Kairos opera solo su interi.
- ~~**`size_t`, `ptrdiff_t`, `intptr_t`, `uintN_t`**~~ — ora disponibili via `mnemo/fake_include/{stddef,stdint}.h` (auto-incluse). Tutti aliasati a `int` / `unsigned int`.
- ~~**`enum` come tipo esplicito di variabile**~~ — `enum Color c = GREEN;` funziona (testato).

### Puntatori

- ~~**Aritmetica puntatore**~~: `p + 1`, `p++`, `p - q`, `*(p+i)` ora supportati su array (mappati a `a[i]`).
- ~~**Puntatori multi-livello**~~: `int **q = &p; **q` funziona (testato).
- **`void *`** — non supportato; puntatori sono typed.
- ~~**`const`, `volatile`, `restrict` qualifiers**~~: testato OK (parser tollera, codice compila e produce valore corretto; semantica enforce non implementata).
- **Pointer-to-array, pointer-to-function** come tipi compositi: solo function pointer compile-time risolto (`p = f` o `&f` con `f` same-file).

### Array

- **VLA (variable-length array)**: `int a[n]` con `n` runtime non supportato.
- **Array element count > 1024** (`ARR_MAX`).
- **Array multidimensionali dinamici** — solo dimensioni costanti compile-time.
- ~~**Designated initializers 1D**~~: `int a[5] = {[2]=42, [4]=99};` ora supportato (incluso mix posizionale + designated `{1,2,[4]=50,60}`).
- ~~**Designated init multi-D**~~: `int m[3][3] = {[0][0]=1, [1][1]=5}` ora supportato (full-index designator `[r][c]`; nested InitList non ancora).
- ~~**Designated init struct**~~: `struct P p = {.x=1, .y=2};` ora supportato (mix posizionale + named `{100, .z=300}` ok).
- ~~**ArrayRef multi-D senza `*` esplicito nel sorgente**~~: bug collaterale risolto — `m[i][j]` ora autoinclude `mul.kairos` (lowering del calcolo riga-maggiore usa `__mn_mul_into`).
- **Compound literals**: `(int[]){1,2,3}` non supportato.

### Funzioni

- **Variadic user functions**: definire `int f(int n, ...)` non supportato. `printf` è caso speciale builtin.
- **Function pointer runtime** — solo compile-time resolved.
- **Nested function definitions** (estensione GCC).
- **Old-style K&R function declarations**.

### Control flow

- **`goto`** — non supportato (rompe reversibilità).
- **`setjmp` / `longjmp`** — non supportati.
- **`switch` con body non-block**: `switch(x) case 1: …;` deve essere `switch(x) { case 1: … }`.
- **`break` nested in `if` verso switch esterno**: errore.
- ~~**`continue` complesso in loop annidati**~~: testato OK (continue verso inner/outer match gcc).
- ~~**Fall-through `case`** senza `break` esplicito~~: testato OK (fall-through pieno e parziale match gcc; `case` vuoto con solo `break` esplicito).

### Storage / linkage

- **`static` locali** — non accumula valore tra chiamate (testato: f() ritorna sempre 1 invece di 1,2,3). Treated as regular local; semantica statefulness non implementata.
- **`extern` con definizione altrove** — solo dichiarazioni file-scope.
- ~~**`register`, `auto` keywords**~~: testato OK (ignorate, codice compila e produce valore corretto).
- **Translation unit multipli** — solo single-file compilation.
- **`#include` di header utente** — `gcc -E -DMNEMO` espande, ma struct/typedef da altri header limitate.

### Struct / union

- **Bit-fields**: `unsigned x : 3;` non supportato.
- **Anonymous struct/union**.
- ~~**Nested struct** (es. `struct Outer { struct Inner a; ...}`)~~: field access `p.a.x` ora supportato (flattening ricorsivo: `_flatten_struct_fields` espande sub-struct by-name in storage locals piatti `o__a__x`). Init list designato struct annidato ancora non testato a fondo.
- **Struct con array a lunghezza variabile** (flexible array members).
- **Nested struct initializer** (`Pair p = {{1,2},{3,4}};`): "troppi elementi" — flat init `Point p = {3,4}` OK.
- **`offsetof`** macro.

### Stdlib

- **`<stdio.h>`** — solo `printf` (sottoinsieme): `%d`, `%u`, `%x`, `%c`, `%s` letterali. Niente `scanf`, `fopen`, `fprintf`, `puts`, ecc.
- **`<stdlib.h>`** — `malloc`/`free` via ptr_pool (con limite size). Niente `calloc`, `realloc`, `atoi`, `exit`.
- **`<string.h>`** — niente `strcmp`, `strlen`, `memcpy`, ecc.
- **`<math.h>`** — niente FP libs.
- **`<stdarg.h>`** — non supportato (no variadic user).
- **`<time.h>`, `<unistd.h>`, `<sys/*>`** — non supportati.

### Misc

- **Inline asm** (`__asm__`, `asm volatile`) — non supportato.
- **`__attribute__`, `__builtin_*`** — non supportati.
- **`_Generic`** (C11) — non supportato.
- **`_Alignas`, `_Alignof`** — non supportati.
- **Complex numbers** (`_Complex`) — non supportati.
- **`_Atomic`** — non supportati (concorrenza solo via mutex π).
- **`argv` POSIX** — `int main(int argc, char **argv)` accettato sintatticamente ma `argv` è stub: niente argomenti command-line reali.
- **`errno`, signal handling** — non supportati.

### Semantica reversibile (vincoli speciali Mnemo)

- **Side effects con risultato non-restored**: `x = f(x)` dove `f` ha effetti → richiede uncall implicit.
- **Operatori non-reversibili** (`/`, `%`) — lib reversibili (`__mn_divmod_nonneg`) gestiscono cases positivi; segno tramite guardia bit.
- **`==`, `!=`, `<`, `>` etc. come espressioni** — solo come condizione `if` / loop guard.
- **Casts scalari espliciti** — `(int)x`, `(long)x`, `(unsigned short)x` ecc ora accettati (no-op nella VM word-size). Era limitato a int↔bool↔unsigned int.
- **Memory aliasing arbitrario** — caller-callee mem cell aliasing non sempre supportato.
- **Ricorsione diretta NON in parallel2/opt-uncall**: `int f(int n) { return n + f(n-1); }` chiamata direttamente da main ritorna 0. Funziona solo wrappata in parallel2(f, g) o via opt-uncall su callee non-self.
- **Array param `int *a`**: il callee deve dichiarare `int a[N]` (size esplicita); `int *a` come parametro array fallisce "'a' non è un array dichiarato".

---

## Storico

(precedenti debug encrypt opt-uncall — risolti via guardie divmod / bit_k_signed / move_int loop inversion)
