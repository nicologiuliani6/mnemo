/* generic_scope_block_a.c
 * Scope annidato: shadowing di `x` nel blocco interno (stesso identificatore).
 */
#include "compat_runtime.h"

int main(void) {
    int x;
    int out;

    x = 5;
    out = x;
    {
        int x;
        x = 99;
        out = out + x;
    }
    out = out + x;

    printf("%d\n", out);
    return out;
}
