/* generic_malloc_free.c
 * Alloca due celle, scrive/legge, libera e ristampa risultato.
 */
#include "compat_runtime.h"

int main(void) {
    int *x;
    int out;

    x = (int *)malloc(4);
    *x = 21;
    out = *x * 2;

    printf("%d\n", out);

    free((void *)x);
    return out - 40;
}
