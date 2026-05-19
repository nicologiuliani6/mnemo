/* generic_intn_types.c
 * int8_t/int32_t/uint16_t/uint64_t aliasati a int/unsigned via fake stdint.h.
 */
#include "compat_runtime.h"
#include <stdint.h>

int main(void) {
    int8_t a;
    int32_t b;
    uint16_t c;
    uint64_t d;
    int r;

    a = 7;
    b = 100;
    c = 50;
    d = 200;
    r = a + b + (int)c + (int)d;

    printf("%d\n", r);
    return r;
}
