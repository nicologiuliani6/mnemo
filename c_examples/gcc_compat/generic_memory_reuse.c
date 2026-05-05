/* generic_memory_reuse.c
 * malloc/free/malloc e verifica del valore scritto.
 */
#include "compat_runtime.h"

int main(void) {
    int *a;
    int *p;
    int out;

    a = (int *)malloc(4);
    *a = 11;
    p = a;
    *p = *p + 9;
    out = *p;

    printf("%d\n", out);
    free((void *)a);
    return out - 10;
}
