/* REGRESSION: opt-uncall su funzione che scrive attraverso un ptr-param dentro
 * un loop (malloc + *out=…). Storicamente escluso (pool_uncall_blocked); ora
 * opt'd grazie a:
 *  - fix VM branch_trace LIFO (l'IF ibrido del *out store statico finiva nel
 *    ramo sbagliato in inverse: Janus.c/vm_invert.h);
 *  - azzeramento dei temp di snapshot dopo l'XOR-swap (le celle non modificate
 *    dal callee, es. il contatore di loop nello snapshot a range completo,
 *    lasciavano il temp != 0 → corruzione cross-iter).
 * Atteso: 90 (2*(0+1+...+9)). */
#ifdef MNEMO
int printf(const char *fmt, ...);
void *malloc(unsigned n);
#else
#include <stdio.h>
#include <stdlib.h>
#endif
void fill(int *out, int v) { int *p = malloc(4); p[0] = v * 2; *out = p[0]; }
int main(void) {
    int sum = 0;
    for (int i = 0; i < 10; i++) { int r = 0; fill(&r, i); sum += r; }
    printf("%d\n", sum);
    return 0;
}
