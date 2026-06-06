/* generic_expr_precedence_a.c
 * Precedenza: * prima di +.
 */
#include "compat_runtime.h"

int main(void) {
    int out;

    out = 2 + 3 * 4;
    printf("%d\n", out);
    return out;
}
