/* generic_enum_a.c
 * Enum base usato in switch.
 */
#include "compat_runtime.h"

enum Mode {
    MODE_OFF = 0,
    MODE_ON = 1
};

int main(void) {
    enum Mode m;
    int out;

    m = MODE_ON;
    out = 0;
    switch (m) {
        case MODE_OFF:
            out = 10;
            break;
        case MODE_ON:
            out = 22;
            break;
        default:
            out = 99;
            break;
    }

    printf("%d\n", out);
    return out - 20;
}
