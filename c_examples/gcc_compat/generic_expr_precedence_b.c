/* generic_expr_precedence_b.c
 * Parentesi su precedenza mista.
 */
#include "compat_runtime.h"

int main(void) {
    int out;

    out = (2 + 3) * (10 - 6);
    printf("%d\n", out);
    return out;
}
