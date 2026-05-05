/* generic_struct_init_list.c — init struct con { … } */
#include "compat_runtime.h"

typedef struct {
  int a;
  int b;
} Pair;

int main(void) {
  Pair p = {2, 40};
  printf("%d\n", p.a + p.b);
  return p.a + p.b;
}
