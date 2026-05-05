/* generic_if_nested_a.c
 * if annidati con confronto multiplo.
 */
#include "compat_runtime.h"

int main(void) {
    int a;
    int b;
    int out;

    a = 8;
    b = 3;
    out = 0;
    if (a > 0) {
        if (b < 5) {
            out = 17;
        } else {
            out = 18;
        }
    } else {
        out = 19;
    }

    printf("%d\n", out);
    return out;
}
