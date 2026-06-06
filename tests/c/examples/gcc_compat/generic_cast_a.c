/* generic_cast_a.c
 * Cast di ritorno malloc verso int*.
 */
#include "compat_runtime.h"

int main(void) {
    int *p;
    int out;

    p = (int *)malloc(4);
    *p = 12;
    out = *p + 8;
    printf("%d\n", out);
    free((void *)p);
    return out - 10;
}
