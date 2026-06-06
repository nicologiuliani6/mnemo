/* generic_switch_math_b.c
 * switch con aggiornamento stato.
 */
#include "compat_runtime.h"

int main(void) {
    int state;
    int out;

    state = 0;
    out = 5;

    switch (state) {
        case 0:
            out = out + 7;
            break;
        case 1:
            out = out + 8;
            break;
        default:
            out = out + 9;
            break;
    }

    printf("%d\n", out);
    return out;
}
