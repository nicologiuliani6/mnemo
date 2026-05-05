/* generic_compound_assign_b.c
 * Sequenza di += -= *= e ^= su scalare.
 */
#include "compat_runtime.h"

int main(void) {
    int x;

    x = 9;
    x += 4;
    x *= 3;
    x -= 5;
    x ^= 2;

    printf("%d\n", x);
    return x;
}
