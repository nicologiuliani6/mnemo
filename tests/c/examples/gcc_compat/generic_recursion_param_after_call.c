/* generic_recursion_param_after_call.c — self-ricorsione con risultato della
 * call legato a un local var e parametro usato DOPO la call. Regression del
 * fix _lower_funccall_with_ret (snapshot/restore degli slot-arg per self-rec):
 * senza il fix `n` veniva letto come 0 (fact(6) → 1 invece di 720).
 */
#include "compat_runtime.h"

int fact(int n) {
  if (n <= 1) return 1;
  int t = fact(n - 1);
  return n * t;
}

int main(void) {
  int r = fact(6);
  printf("%d\n", r);
  return r % 256;
}
