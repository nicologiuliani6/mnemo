/* BUG/limite: `char`/`unsigned char` aliasati a `int` (vedi CLAUDE.md) →
 * l'aritmetica non wrappa a 8 bit. `unsigned char c=250; c+=10;` dà 260 invece
 * di 4 (256-wrap). Per matchare gcc servirebbe mascherare a 0xFF gli assegnamenti
 * a variabili char dopo aritmetica. Impatta molti programmi char/stringhe →
 * va valutato con cura (rischio regressione sulle string-ops). Atteso 4.
 */
#ifdef MNEMO
int printf(const char *fmt, ...);
#else
#include <stdio.h>
#endif
int main(void){
    unsigned char c = 250;
    c += 10;
    printf("%d\n", c);
    return 0;
}
