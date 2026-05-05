/* generic_unsigned_b.c
 * Comparazione unsigned in if.
 */
#include "compat_runtime.h"

int main(void) {
    unsigned int x;
    unsigned int y;
    int out;

    x = 3u;
    y = 5u;
    out = 0;
    if (y > x) {
        out = 12;
    } else {
        out = 99;
    }

    printf("%d\n", out);
    return out;
}
