/* generic_loop_dowhile_b.c
 * do-while con prodotto controllato.
 */
#include "compat_runtime.h"

int main(void) {
    int i;
    int p;

    i = 1;
    p = 1;
    do {
        p = p * 2;
        i = i + 1;
    } while (i < 5);

    printf("%d\n", p);
    return p / 4;
}
