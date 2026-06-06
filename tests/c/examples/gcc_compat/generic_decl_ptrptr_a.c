/* generic_decl_ptrptr_a.c
 * Dichiarazione int** e doppio dereference.
 */
#include "compat_runtime.h"

int main(void) {
    int x;
    int *p;
    int **pp;
    int out;

    x = 13;
    p = &x;
    pp = (int **)&p;
    out = **pp;

    printf("%d\n", out);
    return out;
}
