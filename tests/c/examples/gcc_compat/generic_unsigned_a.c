/* generic_unsigned_a.c
 * Calcolo base con unsigned.
 */
#include "compat_runtime.h"

int main(void) {
    unsigned int a;
    unsigned int b;
    unsigned int c;
    int out;

    a = 7u;
    b = 9u;
    c = a * b;
    out = c - 60u;

    printf("%u\n", c);
    return out;
}
