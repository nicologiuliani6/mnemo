/* generic_expr_unary_plus_a.c
 * Unary plus su literal.
 */
#include "compat_runtime.h"

int main(void) {
    int out;

    out = +7;
    printf("%d\n", out);
    return out;
}
