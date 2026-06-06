/* generic_expr_bitnot_b.c
 * Unary ~ in espressione.
 */
#include "compat_runtime.h"

int main(void) {
    int x;
    int y;

    x = 6;
    y = ~x;
    printf("%d\n", y);
    return y + 10;
}
