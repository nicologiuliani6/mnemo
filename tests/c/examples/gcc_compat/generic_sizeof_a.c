/* generic_sizeof_a.c
 * sizeof su scalare.
 */
#include "compat_runtime.h"

int main(void) {
    int n;

    n = sizeof(int);
    printf("%d\n", n);
    return n;
}
