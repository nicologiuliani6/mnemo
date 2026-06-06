/* REGRESSION: ricorsione mutua. Storicamente crashava la VM
 * (`PUSH: variabile '__mn_e1' è NULL`): is_even→is_odd→is_even ri-entrava nel
 * frame BASE di is_even, e il delocal della call interna liberava i LOCAL int
 * condivisi della call esterna. Fix VM (Janus.c): clona il frame anche per la
 * re-entrancy mutua (contatore Frame.active), non solo per la self-rec.
 * is_even(10)=1, is_odd(7)=1.
 */
#ifdef MNEMO
int printf(const char *fmt, ...);
#else
#include <stdio.h>
#endif
int is_odd(int n);
int is_even(int n){ return n==0 ? 1 : is_odd(n-1); }
int is_odd(int n){ return n==0 ? 0 : is_even(n-1); }
int main(void){ printf("%d %d\n", is_even(10), is_odd(7)); return 0; }
