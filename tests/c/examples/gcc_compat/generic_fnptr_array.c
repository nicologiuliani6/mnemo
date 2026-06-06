/* generic_fnptr_array.c — array di puntatori a funzione, indice costante,
 * risolto a compile-time. */
#include "compat_runtime.h"
int add(int a, int b){ return a + b; }
int sub(int a, int b){ return a - b; }
int mul(int a, int b){ return a * b; }
int main(void){
  int (*ops[3])(int, int) = {add, sub, mul};
  int s = ops[0](5, 3) + ops[1](5, 3) + ops[2](5, 3);  /* 8+2+15=25 */
  printf("%d\n", s);
  return s & 0xFF;
}
