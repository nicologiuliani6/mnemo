/* `a * NEG_CONST` con NEG_CONST < 0: riscritto come `-(a * |NEG_CONST|)`
   per evitare loop infinito in `__mn_mul_into` (assume b>=0). */
#include <stdio.h>

int main(void) {
    int a = 7;
    int b = a * -2;
    int c = 3 * -5;
    int d = a * -1;
    int e = (a + 1) * -3;
    int f = a * -10;
    printf("%d %d %d %d %d\n", b, c, d, e, f);
    return 0;
}
