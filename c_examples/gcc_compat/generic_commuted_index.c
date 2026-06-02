/* generic_commuted_index.c — indice commutato N[a] == a[N]. */
#include "compat_runtime.h"
int main(void){
  int a[4] = {10, 20, 30, 40};
  printf("%d %d %d\n", 0[a], 2[a], 3[a]);   /* 10 30 40 */
  return (0[a] + 2[a]) & 0xFF;
}
