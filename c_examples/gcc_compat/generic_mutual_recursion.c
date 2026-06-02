/* generic_mutual_recursion.c — ricorsione mutua con risultato della call
 * legato a un local e parametro usato DOPO la call. Regression doppia:
 *  (VM) clone del frame su re-entrancy mutua (Frame.active);
 *  (lower) snapshot/restore delle celle del chiamante vive attraverso una call
 *          dentro un ciclo ricorsivo (self O mutuo).
 * ev(6)=6+5+4+3+2+1=21.
 */
#include "compat_runtime.h"

int od(int n);
int ev(int n) { if (n == 0) return 0; int t = od(n - 1); return n + t; }
int od(int n) { if (n == 0) return 0; int t = ev(n - 1); return n + t; }

int main(void) {
  int r = ev(6);
  printf("%d\n", r);
  return r % 256;
}
