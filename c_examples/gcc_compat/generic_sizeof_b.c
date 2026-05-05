/* generic_sizeof_b.c
 * sizeof su array locale.
 */
#include "compat_runtime.h"

int main(void) {
    int v[3];
    int n;

    v[0] = 1;
    v[1] = 2;
    v[2] = 3;
    n = sizeof(v);
    printf("%d\n", n);
    return n / 4;
}
