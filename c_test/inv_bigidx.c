/* Regression guard: store a indice runtime g[i] su array grande (>64 elem)
 * sotto --check-invertibility.
 *
 * Mnemo genera per `G[i]=...` a indice runtime una else-if chain
 * (`if i==0 .. else if i==1 .. else if i==N-1`) profonda quanto l'array.
 * Bug VM: collect_ifs (vm_invert.h) aveva stack interni statici [64] → array
 * > 64 elementi scriveva OOB → corruzione → NULL-deref in resolve_atom /
 * do_eval_if_entry → SIGSEGV non-deterministico. Fix: stack heap-alloc a
 * capacità `max` + guard NULL-slot (var delocal'd ancora nell'indexer → 0).
 * Run con --check-invertibility; deve invertire pulito (exit = G[N-1]&255). */
int G[100];
void fill(void) {
    int i;
    for (i = 0; i < 100; i++) {
        G[i] = i * 2;
    }
}
int main(void) {
    fill();
    return G[99] & 255;   /* 198 */
}
