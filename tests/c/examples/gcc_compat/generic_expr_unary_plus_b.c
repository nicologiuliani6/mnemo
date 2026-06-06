/* generic_expr_unary_plus_b.c
 * Unary plus su variabile.
 */
#include "compat_runtime.h"

int main(void) {
    int x;
    int out;

    x = 14;
    out = +x + 2;
    printf("%d\n", out);
    return out;
}
