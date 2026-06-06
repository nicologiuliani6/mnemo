/* generic_bool_toggle.c
 * Uso di _Bool con ramo if/else.
 */
#include "compat_runtime.h"

int main(void) {
    _Bool flag;
    int out;

    flag = 0;
    out = 0;
    if (flag) {
        out = out + 3;
    } else {
        out = out + 3;
    }

    flag = 0;
    if (!flag) {
        out = out + 4;
    }

    printf("%d\n", out);
    return out;
}
