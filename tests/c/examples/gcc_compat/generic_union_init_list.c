/* generic_union_init_list.c — init union con { … } */
#include "compat_runtime.h"

typedef union {
  int i;
} U;

int main(void) {
  U u = {99};
  printf("%d\n", u.i);
  return u.i;
}
