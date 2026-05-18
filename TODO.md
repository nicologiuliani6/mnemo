# TODO

## OPEN

### [P3] opt-uncall self-recursion (fibonacci → fibonacci)

**Stato**: skip se `caller == callee` (mnemo c_lower.py `self_rec` guard).

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

## Storico

(precedenti debug encrypt opt-uncall — risolti via guardie divmod / bit_k_signed / move_int loop inversion)
