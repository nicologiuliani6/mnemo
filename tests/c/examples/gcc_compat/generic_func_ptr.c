/* generic_func_ptr.c — puntatore a funzione risolto a compile-time */
#include "compat_runtime.h"

int doub(int x) { return x + x; }

int main(void) {
  int (*f)(int) = doub;
  int (*g)(int) = &doub;
  int a = f(3);
  int b = (*g)(4);
  printf("%d\n", a + b);
  return a + b;
}
