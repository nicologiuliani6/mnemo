/* generic_params_by_value_a.c
 * Passaggio per valore su int.
 */
#include "compat_runtime.h"

int inc_twice(int x) {
    x = x + 1;
    x = x + 1;
    return x;
}

int main(void) {
    int a;
    int b;

    a = 8;
    b = inc_twice(a);
    printf("%d %d\n", a, b);
    return b - a;
}
