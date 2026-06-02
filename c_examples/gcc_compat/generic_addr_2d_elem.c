/* generic_addr_2d_elem.c — indirizzo di elemento di array 2D: &m[i][j].
 * Regression: prima `&` supportava solo `&array[idx]` 1D.
 */
#include "compat_runtime.h"

int main(void) {
  int m[2][3] = {{1, 2, 3}, {4, 5, 6}};
  int *p = &m[0][0];
  int *q = &m[1][1];
  int s = 0, i;
  for (i = 0; i < 6; i++) s += p[i];   /* 1..6 = 21 */
  printf("%d %d\n", s, *q);            /* 21 5 */
  return (s + *q) & 0xFF;
}
