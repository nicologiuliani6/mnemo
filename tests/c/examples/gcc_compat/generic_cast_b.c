/* generic_cast_b.c
 * Cast verso void* in free.
 */
#include "compat_runtime.h"

int main(void) {
    int *p;
    int out;

    p = (int *)malloc(4);
    *p = 19;
    out = *p + 1;
    printf("%d\n", out);
    free((void *)p);
    return out;
}
