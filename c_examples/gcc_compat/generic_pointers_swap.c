/* generic_pointers_swap.c
 * Scambio valori via puntatori.
 */
#include "compat_runtime.h"

int main(void) {
    int a;
    int b;
    int t;
    int *pa;
    int *pb;

    a = 4;
    b = 9;
    pa = &a;
    pb = &b;

    t = *pa;
    *pa = *pb;
    *pb = t;

    printf("%d %d\n", a, b);
    return a + b;
}
