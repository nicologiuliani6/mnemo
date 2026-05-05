/* generic_bool_branch.c
 * Usa _Bool in condizioni e stampa risultato.
 */
#include "compat_runtime.h"

int main(void) {
    _Bool cond_a;
    _Bool cond_b;
    int out;

    cond_a = 0;
    cond_b = 0;
    out = 0;

    if (cond_a) {
        out = out + 10;
    }
    if (!cond_b) {
        out = out + 5;
    }

    printf("%d\n", out);
    return out;
}
