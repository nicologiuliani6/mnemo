/* REGRESSION: parametro ripristinato dopo una call self-ricorsiva il cui
 * risultato è legato a un local var. `int t=fact(n-1); return n*t;` — `n`
 * deve restare valido dopo la call. Bug storico: n letto come 0 (gli slot-arg
 * = celle frame del chiamante, sovrascritte dal setup-arg, mai ripristinate).
 * Fix: _lower_funccall_with_ret snapshot+restore degli slot-arg per self-rec.
 * fact(5)=120.
 */
#ifdef MNEMO
int printf(const char *fmt, ...);
#else
#include <stdio.h>
#endif
int fact(int n){ if(n<=1) return 1; int t=fact(n-1); return n*t; }
int main(void){ printf("%d\n", fact(5)); return 0; }
