/* generic_bitwise_negative.c — OR/AND/XOR su interi negativi (bit 31 = segno).
 * Regression del fix lib/bits.kairos: __mn_and_into/__mn_or_into ora gestiscono
 * il bit 31 in complemento a 2 (contributo -2^31). Prima: -5|8 → 2147483643.
 */
#include "compat_runtime.h"

int main(void) {
  int x = -5, y = -1;
  int o = x | 8;     /* -5  */
  int a = y & y;     /* -1  */
  int z = x ^ 1;     /* -6  */
  int n = ~x;        /*  4  */
  int m = x & y;     /* -5  */
  printf("%d %d %d %d %d\n", o, a, z, n, m);
  return (o + a + z + n + m) & 0xFF;
}
