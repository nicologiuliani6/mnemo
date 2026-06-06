/* generic_loop_array.c
 * Array, ciclo for e accumulo.
 */
#include "compat_runtime.h"

int main(void) {
    int v[5];
    int i;
    int acc;

    v[0] = 1;
    v[1] = 2;
    v[2] = 3;
    v[3] = 4;
    v[4] = 5;

    acc = 0;
    for (i = 0; i < 5; i = i + 1) {
        acc = acc + v[i];
    }

    printf("%d\n", acc);
    return acc;
}
