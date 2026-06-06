/* generic_control_switch_a.c
 * switch/case con break espliciti.
 */
#include "compat_runtime.h"

int main(void) {
    int x;
    int out;

    x = 2;
    out = 0;

    switch (x) {
        case 1:
            out = 10;
            break;
        case 2:
            out = 20;
            break;
        default:
            out = 30;
            break;
    }

    printf("%d\n", out);
    return out / 10;
}
