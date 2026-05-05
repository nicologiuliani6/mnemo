/* generic_scope_block_b.c
 * Shadowing nel corpo compound di un for (scope del blocco, non del for-init).
 */
#include "compat_runtime.h"

int main(void) {
    int out;
    int x;
    int i;

    out = 0;
    x = 2;
    for (i = 0; i < 1; i++) {
        int x;
        x = 100;
        out = out + x;
    }
    out = out + x;

    printf("%d\n", out);
    return out;
}
