/* generic_array_2d_a.c
 * Array 2D con assegnazioni esplicite.
 */
#include "compat_runtime.h"

int main(void) {
    int m[2][3];
    int out;

    m[0][0] = 1;
    m[0][1] = 2;
    m[0][2] = 3;
    m[1][0] = 4;
    m[1][1] = 5;
    m[1][2] = 6;

    out = m[0][2] + m[1][1];
    printf("%d\n", out);
    return out;
}
