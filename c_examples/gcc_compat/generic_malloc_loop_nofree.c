/* generic_malloc_loop_nofree.c
 * Regression: malloc dentro un loop a bound COSTANTE senza free (blocchi
 * accumulati). L'auto-sizing del pool ora moltiplica le celle per il
 * trip-count del loop statico (prima contava il malloc 1 volta → pool
 * sottodimensionato → risultato errato).
 */
#include "compat_runtime.h"

int main(void) {
    int s = 0, i;
    for (i = 0; i < 6; i++) {
        int *p = (int *)malloc(sizeof(int) * 2);
        p[0] = i;
        p[1] = i * 10;
        s += p[0] + p[1];
    }
    printf("%d\n", s);   /* (0+10+20+30+40+50)+(0+1+2+3+4+5) = 150+15 = 165 */
    return 0;
}
