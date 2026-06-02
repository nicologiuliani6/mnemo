/* BUG (semantica tipi): Mnemo è internamente all-signed-int e non applica le
 * usual arithmetic conversions del C. `unsigned a=10; int b=-20;` → `a+b` ha
 * tipo unsigned → `(a+b)<0` è SEMPRE falso in C ("pos"). Mnemo fa un confronto
 * signed (-10<0 → "neg"). Il valore (%u/%d) è corretto; sbaglia solo il
 * confronto. Vedi anche c_test/bug_uchar_wrap.c (stessa radice).
 */
#ifdef MNEMO
int printf(const char *fmt, ...);
#else
#include <stdio.h>
#endif
int main(void){
    unsigned a = 10;
    int b = -20;
    if ((a + b) < 0) printf("neg\n"); else printf("pos\n");
    return 0;
}
