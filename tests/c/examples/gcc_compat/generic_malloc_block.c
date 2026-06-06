/* generic_malloc_block.c
 * Regression: malloc(sizeof(int)*N) con N > 4 deve dimensionare il pool a N
 * celle. Prima _infer_ptr_pool_size contava i call-site (non la size) → blocco
 * troncato a default → p[i] oltre l'ultima cella = no-op → risultato errato.
 */
#include "compat_runtime.h"

int main(void) {
    int *p = (int *)malloc(sizeof(int) * 7);
    int i, s = 0;
    for (i = 0; i < 7; i++) p[i] = (i + 1) * 3;
    for (i = 0; i < 7; i++) s += p[i];
    printf("%d\n", s);   /* 3+6+9+12+15+18+21 = 84 */
    free((void *)p);
    return 0;
}
