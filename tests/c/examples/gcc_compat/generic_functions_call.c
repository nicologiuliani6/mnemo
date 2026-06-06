/* generic_functions_call.c
 * Chiamate funzione con ritorno int.
 */
#include "compat_runtime.h"

int twice(int x) {
    return x * 2;
}

int add3(int x) {
    return x + 3;
}

int main(void) {
    int a;
    int b;

    a = twice(5);
    b = add3(a);

    printf("%d\n", b);
    return b;
}
