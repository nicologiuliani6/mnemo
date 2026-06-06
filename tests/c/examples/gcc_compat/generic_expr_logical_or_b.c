/* generic_expr_logical_or_b.c
 * || come espressione con risultato 0/1.
 */
#include "compat_runtime.h"

int main(void) {
    int a;
    int b;
    int out;

    a = (0 > 1) || (4 > 1);
    b = (0 > 1) || (1 > 4);
    out = a * 10 + b;

    printf("%d\n", out);
    return out;
}
