/* generic_self_mutual_recursion.c — funzione raggiunta SIA da self- SIA da
 * mutua-ricorsione, profondità interlacciate. Verifica che lo schema di
 * frame-key (self @N + mutua Frame.active) non collida. */
#include "compat_runtime.h"
int b(int n);
int a(int n){ if(n<=0) return 1; return a(n-1) + b(n-1) + a(n-2); }
int b(int n){ if(n<=0) return 0; return a(n-1) + b(n-2); }
int main(void){
  int s = 0, i;
  for (i = 0; i < 8; i++) s += a(i) + b(i);
  printf("%d\n", s);              /* 476 */
  return s & 0xFF;
}
