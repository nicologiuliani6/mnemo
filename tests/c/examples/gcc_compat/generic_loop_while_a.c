/* generic_loop_while_a.c
 * while con accumulo crescente.
 */
#include "compat_runtime.h"

int main(void) {
    int i;
    int acc;

    i = 0;
    acc = 0;
    while (i < 5) {
        acc = acc + i;
        i = i + 1;
    }

    printf("%d\n", acc);
    return acc;
}
