/* generic_params_by_value_b.c
 * Passaggio misto: valore (int) e riferimento (int*).
 */
#include "compat_runtime.h"

int combine(int x, int y) {
    return x * 2 + y;
}

void bump(int *p) {
    *p = *p + 5;
}

int main(void) {
    int a;
    int b;
    int out;

    a = 6;
    b = 1;
    bump(&b);
    out = combine(a, b);
    printf("%d\n", out);
    return out - 10;
}
