/* generic_lvalue_incdec.c — ++/-- su array, *p, campo struct */
#include "compat_runtime.h"

typedef struct {
  int u;
} Box;

int main(void) {
  int a[2];
  int *p;
  Box b;

  a[0] = 5;
  a[1] = 7;
  a[0]++;
  a[1]--;

  p = (int *)malloc(sizeof(int));
  *p = 4;
  (*p)++;

  b.u = 2;
  b.u++;

  printf("%d\n", a[0] + a[1] + *p + b.u);
  free(p);
  return 0;
}
