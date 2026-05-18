# TODO

## OPEN

### [P3] opt-uncall self-recursion (fibonacci → fibonacci)

**Stato**: skip se `caller == callee` (mnemo c_lower.py).

**Causa**: VM uncall sul frame depth N quando call su depth N+1 in corso → frame state stack management complesso.

**Progress**:
- ✅ VM `exec_branch_inverse` CALL handler ora gestisce caso ricorsivo (clone_frame_for_depth + invert_op_to_line) — kairos 0166749.
- ❌ Forward `__mn_e12 ^= __mn_mem9` su `sumto@5` fallisce con var NULL anche se LOCAL e DELOCAL hanno girato per quel frame. Trace mostra XOR SNAP eseguito su sumto@4 (caller) PRIMA che END_PROC restore fname a sumto@4 → forse problema fname tracking o clone re-use con var già delocaled. Non root-caused.

**Per attivare**: capire perché XOREQ forward in caller (sumto@4) sembra valutarsi nel frame sumto@5 (post-delocal). Probabilmente DELOCAL spuria o END_PROC manca per via dell'IF-then-fi struttura su base-case.

Tempo stimato: 4-8 ore.

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
