/* generic_bitwise_and.c
 * Operatore AND bitwise su interi (copre __mn_and_into / bits.kairos).
 */
#include "compat_runtime.h"

int main(void) {
    int a;
    int b;
    int z;

    a = 15;
    b = 51;
    z = a & b;

    printf("%d\n", z);
    return z;
}
