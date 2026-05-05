/* generic_array_2d_b.c
 * Array 2D con doppio loop.
 */
#include "compat_runtime.h"

int main(void) {
    int m[2][2];
    int i;
    int j;
    int acc;

    acc = 0;
    for (i = 0; i < 2; i = i + 1) {
        for (j = 0; j < 2; j = j + 1) {
            m[i][j] = (i + 1) * (j + 2);
            acc = acc + m[i][j];
        }
    }

    printf("%d\n", acc);
    return acc;
}
