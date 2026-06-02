/* generic_struct_array_init.c — init di array di struct con graffe annidate.
 * Regression: prima `array di struct: inizializzatore non supportato`.
 */
#include "compat_runtime.h"

struct P { int x, y; };

int main(void) {
  struct P a[3] = {{1, 2}, {3, 4}, {5, 6}};
  struct P b[3] = {{7, 8}};   /* init parziale: b[1],b[2] = 0 */
  int s = 0, i;
  for (i = 0; i < 3; i++) s += a[i].x + a[i].y + b[i].x + b[i].y;
  printf("%d\n", s);
  return s & 0xFF;
}
