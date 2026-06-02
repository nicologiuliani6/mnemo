/* generic_malloc_in_function.c — malloc dentro funzioni non-main + scrittura via
 * puntatore-parametro + malloc cross-funzione. Regression del fix: __mn_pool_ctr
 * threaded by-ref tra le call (allocazioni sequenziali, niente collisione con la
 * regione nominata né tra funzioni).
 */
#include "compat_runtime.h"

void setv(int *out) {
  int *p = malloc(4);
  p[0] = 99;
  *out = p[0];
}
void helper(int *out) {
  int *q = malloc(8);
  q[0] = 5; q[1] = 6;
  *out = q[0] + q[1];
}
int main(void) {
  int r = 0; setv(&r);
  int *p = malloc(4); p[0] = 100;
  int h = 0; helper(&h);
  printf("%d %d %d\n", r, p[0], h);   /* 99 100 11 */
  return (r + p[0] + h) & 0xFF;
}
