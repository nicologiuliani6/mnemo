/* generic_union_basic_a.c
 * Union con campo int.
 */
#include "compat_runtime.h"

typedef union {
    int i;
    unsigned int u;
} UNum;

int main(void) {
    UNum u;
    int out;

    u.i = 14;
    out = u.i + 6;
    printf("%d\n", out);
    return out - 10;
}
