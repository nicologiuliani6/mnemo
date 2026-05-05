/* generic_union_basic_b.c
 * Union con scrittura/lettura del medesimo campo.
 */
#include "compat_runtime.h"

typedef union {
    int left;
    int right;
} UPair;

int main(void) {
    UPair u;
    int out;

    u.left = 3;
    u.left = u.left * 7;
    out = u.left + 1;
    printf("%d\n", out);
    return out;
}
