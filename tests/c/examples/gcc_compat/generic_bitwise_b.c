/* generic_bitwise_b.c
 * XOR composto ( ^= ) su interi.
 */
#include "compat_runtime.h"

int main(void) {
    int a;
    int out;

    a = 6;
    a ^= 3;
    out = a + 1;

    printf("%d\n", out);
    return out;
}
