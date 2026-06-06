/* generic_array_update.c
 * Aggiornamento array in loop + accumulo.
 */
#include "compat_runtime.h"

int main(void) {
    int v[4];
    int i;
    int acc;

    v[0] = 2;
    v[1] = 4;
    v[2] = 6;
    v[3] = 8;

    for (i = 0; i < 4; i = i + 1) {
        v[i] = v[i] + 1;
    }

    acc = v[0] + v[1] + v[2] + v[3];
    printf("%d\n", acc);
    return acc;
}
