/* generic_expr_not_a.c
 * Unary ! in espressione aritmetica.
 */
#include "compat_runtime.h"

int main(void) {
    int a;
    int b;
    int out;

    a = !0;
    b = !7;
    out = a * 10 + b;
    printf("%d\n", out);
    return out;
}
