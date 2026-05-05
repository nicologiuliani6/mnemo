/* generic_compound_assign_a.c
 * Assegnamenti composti supportati su scalari.
 */
#include "compat_runtime.h"

int main(void) {
    int x;

    x = 10;
    x += 5;
    x -= 3;
    x *= 2;
    x ^= 7;

    printf("%d\n", x);
    return x;
}
