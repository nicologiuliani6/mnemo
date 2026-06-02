/* REPRO bug aperto: ricorsione mutua → VM crash `PUSH: variabile '__mn_e1'
 * è NULL`. is_even/is_odd si chiamano a vicenda; temp non dichiarato nel
 * codegen cross-call. Atteso "1 0".  (Distinto dal fix self-rec.)
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
