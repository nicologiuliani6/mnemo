/* generic_unsigned_cmp_zero.c — confronto unsigned vs 0 (usual arithmetic
 * conversions). `unsigned a; int b; (a+b)<0` è sempre falso in C. Regression
 * del fold _fold_unsigned_cmp_zero (Mnemo è all-signed e sbagliava).
 */
#include "compat_runtime.h"
int main(void){
  unsigned a = 10; int b = -20;
  int r1 = ((a + b) < 0);    /* 0 */
  int r2 = ((a + b) >= 0);   /* 1 */
  unsigned u = 7;
  int r3 = (u > 0);          /* 1 */
  int r4 = (0 < u);          /* 1 */
  int s = -5;
  int r5 = (s < 0);          /* 1 (signed, invariato) */
  printf("%d %d %d %d %d\n", r1, r2, r3, r4, r5);
  return r1 + r2 + r3 + r4 + r5;
}
