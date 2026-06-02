/* generic_unsigned_cmp_zero.c — confronti unsigned vs 0 NON tautologici
 * (gcc -Wtype-limits warna su `unsigned < 0`/`>= 0`, quindi quelli stanno in
 * c_test/bug_mixed_sign_cmp.c). Qui: `u > 0`, `u <= 0`, `0 < u`, signed `< 0`.
 * Regression del fold _fold_unsigned_cmp_zero + invarianza dei confronti signed.
 */
#include "compat_runtime.h"
int main(void){
  unsigned u = 7, z = 0;
  int r1 = (u > 0);     /* 1 */
  int r2 = (z <= 0);    /* 1 */
  int r3 = (0 < u);     /* 1 */
  int r4 = (z > 0);     /* 0 */
  int s = -5;
  int r5 = (s < 0);     /* 1 (signed, invariato) */
  printf("%d %d %d %d %d\n", r1, r2, r3, r4, r5);
  return r1 + r2 + r3 + r4 + r5;
}
