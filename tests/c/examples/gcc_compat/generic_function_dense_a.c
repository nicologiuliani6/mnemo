/* generic_function_dense_a.c
 * Funzioni annidate con piu parametri.
 */
#include "compat_runtime.h"

int addmul(int a, int b, int c) {
    return (a + b) * c;
}

int adjust(int x) {
    return x - 4;
}

int main(void) {
    int out;

    out = adjust(addmul(2, 3, 5));
    printf("%d\n", out);
    return out;
}
