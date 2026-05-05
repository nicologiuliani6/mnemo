/* generic_struct_fields_a.c
 * Struct con campi scalari e aggiornamento diretto.
 */
#include "compat_runtime.h"

typedef struct {
    int x;
    int y;
} Pair;

int main(void) {
    Pair p;
    int out;

    p.x = 10;
    p.y = 5;
    p.x = p.x + 3;
    p.y = p.y * 2;

    out = p.x + p.y;
    printf("%d\n", out);
    return out - 20;
}
