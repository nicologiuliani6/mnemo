/* `a / NEG_CONST` riscritto come `-(a / |NEG_CONST|)` e
   `a % NEG_CONST` come `a % |NEG_CONST|` (C99: segno di `%` segue
   dividendo). `__mn_divmod_nonneg` / `__mn_mod_nonneg` assumono
   divisore >= 0. */
#include <stdio.h>

int main(void) {
    int a = 10;
    int b = a / -2;       /* -5 */
    int c = a % -3;       /* 1 */
    int d = 15 / -4;      /* -3 */
    int e = 17 % -5;      /* 2 */
    int f = (a + 5) / -3; /* 15 / -3 = -5 */
    int g = (a * 2) % -7; /* 20 % -7 = 6 */
    printf("%d %d %d %d %d %d\n", b, c, d, e, f, g);
    return 0;
}
