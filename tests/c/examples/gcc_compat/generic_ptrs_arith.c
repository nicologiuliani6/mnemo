/* generic_ptrs_arith.c
 * Puntatori base e aggiornamento memoria via dereference.
 */
#include "compat_runtime.h"

int main(void) {
    int a;
    int b;
    int *p;
    int *q;

    a = 7;
    b = 3;
    p = &a;
    q = &b;

    *p = *p + 10;
    *q = (*p - *q) * 2;

    printf("%d %d\n", a, b);
    return b;
}
