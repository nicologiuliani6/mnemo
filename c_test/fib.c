/* fib parallelo: parallel2 con `int *ret` → fallback sequenziale ricorsivo
 * (Mnemo c_lower.py:1888 — vedere `recursive_fallback`). Rewrite in stile
 * canale (mnemo_kairos_pi) bypasserebbe il fallback (esenzione
 * channel-only attiva), ma richiede:
 *   - VM ssend `__mn_kch_*` async-buffered su single-int senza rompere
 *     channel-ref payload di pi_calculus → non implementato in modo
 *     compatibile in questa sessione;
 *   - fix VM `op_jmp` su frame thread ricorsivi (label `FI_NNN` non risolta
 *     in PAR-thread nested → segfault).
 * Mantenuto in forma classica finché VM PAR non gestisce reale ricorsione
 * con canali.
 */

void mnemo_pthread_parallel2(
    void (*a)(int, int *),
    void (*b)(int, int *),
    int arg_a,
    int arg_b,
    int *ret_a,
    int *ret_b
);

int fib(int n, int *ret){
    if(n <= 1){
        *ret += 1;
        return 1;
    }
    int ret1, ret2;
    mnemo_pthread_parallel2(fib, fib, n-1, &ret1, n-2,  &ret2);
    return ret1 + ret2;
}


int main(void){
    return fib(10, (int*)0);
}
