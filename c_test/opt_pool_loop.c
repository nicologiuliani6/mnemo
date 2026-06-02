/* opt-uncall su funzione pool-using (malloc in loop, risultato via globale):
 * ORA ottimizzata (prima esclusa da pool_blk). `mnemo run --opt-uncall-user-calls
 * --vm-stats` mostra cells_max ~dimezzato vs no-opt; risultato + invertibilità
 * intatti. Funzioni che scrivono `*out` su un ptr-param restano escluse
 * (c_test/bug_malloc_in_function.c). work(20) → G=190.
 */
#ifdef MNEMO
int printf(const char *fmt, ...);
void *malloc(unsigned n);
#else
#include <stdio.h>
#include <stdlib.h>
#endif
int G;
void work(int n){
    int acc = 0;
    for (int i = 0; i < n; i++) { int *p = malloc(4); p[0] = i; acc += p[0]; }
    G = acc;
}
int main(void){ work(20); printf("%d\n", G); return 0; }
