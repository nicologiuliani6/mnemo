/* REGRESSION (no gcc -Wextra qui): confronto unsigned vs 0.
 * `unsigned a=10; int b=-20; (a+b)<0` è sempre falso in C (la somma è
 * unsigned). Mnemo era all-signed e dava "neg"; ora fold
 * _fold_unsigned_cmp_zero → "pos". Atteso: pos.
 */
#ifdef MNEMO
int printf(const char *fmt, ...);
#else
#include <stdio.h>
#endif
int main(void){
    unsigned a = 10; int b = -20;
    if ((a + b) < 0) printf("neg\n"); else printf("pos\n");
    return 0;
}
