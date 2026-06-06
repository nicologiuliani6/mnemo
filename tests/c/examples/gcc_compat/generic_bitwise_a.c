/* generic_bitwise_a.c
 * Operatore XOR bitwise su interi.
 */
#include "compat_runtime.h"

int main(void) {
    int a;
    int b;
    int z;

    a = 12; /* 1100 */
    b = 10; /* 1010 */
    z = a ^ b;

    printf("%d\n", z);
    return z;
}
