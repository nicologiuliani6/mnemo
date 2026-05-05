/* generic_switch_math_a.c
 * switch con pre-calcolo aritmetico.
 */
#include "compat_runtime.h"

int main(void) {
    int x;
    int out;

    x = (3 * 2) - 4;
    switch (x) {
        case 1:
            out = 11;
            break;
        case 2:
            out = 12;
            break;
        default:
            out = 13;
            break;
    }

    printf("%d\n", out);
    return out - 10;
}
