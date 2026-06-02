/* REGRESSION: ternario la cui guardia è mutata in un ramo:
 * `x = x ? 1 : (x=2, x+1);`. Storicamente fallimento silenzioso (la `fi`
 * Kairos rivalutava `x!=0` dopo che il ramo aveva cambiato x → inversione
 * rotta). Fix: _lower_if_from_expr materializza la verità in un temp
 * frame-local prima dei rami. Atteso 3.
 */
#ifdef MNEMO
int printf(const char *fmt, ...);
#else
#include <stdio.h>
#endif
int main(void){
    int x = 0;
    x = x ? 1 : (x = 2, x + 1);
    printf("%d\n", x);
    return 0;
}
