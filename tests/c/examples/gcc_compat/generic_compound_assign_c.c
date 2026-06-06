/* generic_compound_assign_c.c
 * Assegnamenti composti su scalare: ^=, <<=, >>=, &=, |=.
 */
#include "compat_runtime.h"

int main(void) {
    int x;

    x = 15;
    x ^= 31;
    x ^= 7;
    x <<= 1;
    x >>= 1;
    x &= 7;
    x |= 8;

    printf("%d\n", x);
    return x;
}
