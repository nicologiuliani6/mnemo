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

**Ipotesi attiva (da verificare)**: errore `XOREQ __mn_e12 NULL` accade durante INVERSE pass (UNCALL del livello opt-uncall), non forward. In quel caso il `frame_name` passato a op_xoreq punta al caller post-DELOCAL: ops_arith.h:60 chiama `get_var(vm, fi, ID, "XOREQ")` con `fi = get_findex(frame_name)` — se frame_name è il caller (post END_PROC) il suo __mn_e12 è stato DELOCAL'd → vars[24]=NULL.

**Test mirato proposto**: aggiungere `fprintf(stderr, "[XOREQ] fname=%s inv=%d\n", frame_name, vm->inversion_depth)` in `op_xoreq` per discriminare forward vs inverse, poi log su `op_local` per __mn_e12 con stesso fname e inv. Se prove di "LOCAL non gira prima di XOREQ" → fix in invert_op_to_line per re-LOCAL slot mancanti. Se "LOCAL gira ma DELOCAL spuria" → fix in flusso UNCALL/END_PROC.

Tempo stimato residuo: 3-6 ore.

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
