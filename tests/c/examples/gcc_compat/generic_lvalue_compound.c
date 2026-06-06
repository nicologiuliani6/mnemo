/* generic_lvalue_compound.c
 * Assegnamenti composti su struct., array[], *p, p->campo.
 */
#include "compat_runtime.h"

typedef struct {
    int x;
    int y;
} Pair;

typedef struct {
    int v;
} Box;

static void box_shlv(Box *p) {
    p->v <<= 2;
}

int main(void) {
    Pair s;
    int a[3];
    int *heap;
    Box b;
    int out;

    s.x = 3;
    s.y = 10;
    s.x += 4;
    s.y *= 2;

    a[0] = 1;
    a[1] = 2;
    a[2] = 3;
    a[0] += 5;
    a[1] <<= 1;

    heap = (int *)malloc(4);
    *heap = 7;
    *heap += 2;

    b.v = 2;
    box_shlv(&b);

    out = s.x + s.y + a[0] + a[1] + a[2] + *heap + b.v;
    /* 7 + 20 + 6 + 4 + 3 + 9 + 8 = 57 */

    printf("%d\n", out);
    free((void *)heap);
    return out - 50;
}
