/* REGRESSION: malloc dentro funzioni non-main + scrittura via puntatore-
 * parametro + malloc cross-funzione. Storicamente errato: __mn_pool_ctr era un
 * local per-funzione che partiva da 0 → malloc su slot < heap_base trattati
 * come celle nominate dal dispatch ibrido → corruzione + *out instradato male
 * (r restava 0). Fix: __mn_pool_ctr threaded by-ref tra le call (param delle
 * funzioni pool-using, posseduto da main come local init heap_base) →
 * allocazioni sequenziali. Atteso 99.
 */
#ifdef MNEMO
int printf(const char *fmt, ...);
void *malloc(unsigned n);
#else
#include <stdio.h>
#include <stdlib.h>
#endif
void setv(int *out){ int *p = malloc(4); p[0] = 99; *out = p[0]; }
int main(void){ int r = 0; setv(&r); printf("%d\n", r); return 0; }
