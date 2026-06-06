/* generic_control_switch_b.c
 * switch con default ultimo e ramo aggiuntivo.
 */
#include "compat_runtime.h"

int main(void) {
    int x;
    int out;

    x = 9;
    out = 1;

    switch (x) {
        case 7:
            out = out + 7;
            break;
        case 8:
            out = out + 8;
            break;
        default:
            out = out + 9;
            break;
    }

    printf("%d\n", out);
    return out;
}
