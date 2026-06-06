/* generic_malloc_concurrent.c
 * Regression: due (e tre) malloc multi-cella vivi contemporaneamente non
 * devono sovrapporsi. Prima __mn_pool_alloc avanzava il contatore di 1 invece
 * che della block-size → i blocchi condividevano celle (risultato errato).
 * Fix: modello block-aware con header (mem{ctr}=nblk, ptr=ctr+1, ctr+=nblk+1).
 */
#include "compat_runtime.h"

int main(void) {
    int *a = (int *)malloc(sizeof(int) * 2);
    int *b = (int *)malloc(sizeof(int) * 3);
    a[0] = 1; a[1] = 2;
    b[0] = 10; b[1] = 20; b[2] = 30;
    printf("%d\n", a[0] + a[1] + b[0] + b[1] + b[2]);  /* 63 */
    free((void *)b);
    free((void *)a);
    return 0;
}
