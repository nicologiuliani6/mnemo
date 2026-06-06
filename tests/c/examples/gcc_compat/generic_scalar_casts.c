/* generic_scalar_casts.c
 * Scalar casts (int)/(long)/(short)/(unsigned) accettati come no-op.
 */
#include "compat_runtime.h"

int main(void) {
    long a;
    short b;
    int c;
    unsigned u;

    a = 100;
    b = 5;
    c = (int)a + (int)b;
    u = (unsigned)c;

    printf("%u\n", u);
    return c;
}
