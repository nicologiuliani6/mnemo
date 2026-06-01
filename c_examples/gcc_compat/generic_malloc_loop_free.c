/* generic_malloc_loop_free.c
 * Regression: malloc + free DENTRO un loop, slot riusato a ogni iterazione.
 * Bug: __mn_pool_free faceva `push(ctr); ctr -= 1` ma op_push azzera la
 * sorgente → ctr = -1 invece di ctr-1 → il contatore pool si corrompeva al
 * riuso e gli slot drift­avano (es. stampa `0 0 2` invece di `0 1 2`).
 */
#include "compat_runtime.h"

int main(void) {
    int i, s = 0;
    for (i = 0; i < 4; i++) {
        int *p = (int *)malloc(sizeof(int));
        *p = i * 7;
        s += *p;
        free((void *)p);
    }
    printf("%d\n", s);   /* 0+7+14+21 = 42 */
    return 0;
}
