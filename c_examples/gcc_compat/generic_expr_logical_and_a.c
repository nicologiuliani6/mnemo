/* generic_expr_logical_and_a.c
 * && come espressione con risultato 0/1.
 */
#include "compat_runtime.h"

int main(void) {
    int a;
    int b;
    int out;

    a = (3 > 1) && (5 > 2);
    b = (3 > 1) && (2 > 5);
    out = a * 10 + b;

    printf("%d\n", out);
    return out;
}
