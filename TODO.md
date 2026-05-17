# TODO

## OPEN

### [P3] `--check-invertibility` su 0-iter loop

**Sintomo**: `for(i=0; i<0; i++) body` esegue 1 skip-iter forward sotto counter-loop lowering. Main exit C semantica differente.

**Causa**: `from cnt == 0` entry sempre vera → loop entrato anche su 0-iter. Body non-guard runs 1 skip.

**Fix**: IIfKairos guard wrap `if init_lc != 0 then loop fi`. Rompe nested IF inverse Janus (blocca P1). Risolvibile dopo P1.

### [P3] opt-uncall self-recursion (fibonacci → fibonacci)

**Stato**: skip se `caller == callee` (mnemo c_lower.py).

**Causa**: VM uncall sul frame depth N quando call su depth N+1 in corso → frame state stack management complesso.

**Per attivare**: in init_clone_frame preservare snap state per depth+1, op_uncall su clone-N invocare invert_op_to_line con depth-aware key.

Tempo stimato: 4-8 ore.

### [P4] Janus `loop_mnemo_deep_increment` calibrato divmod

**Stato**: counter-based loop lowering aggira il bug. deep_peel restano in codice per loop non-counter (rari ora).

**Fix opzionale**: rimuovere `loop_mnemo_deep_increment` + dipendenze `jmp_start_deep` se counter-loop default → vm_invert.h più snello.

---

## DONE (recente)

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
