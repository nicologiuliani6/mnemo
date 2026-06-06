/* `__mn_mul_signed_into` / `__mn_divmod_signed` / `__mn_mod_signed`:
   nuove lib procs reversibili che gestiscono segno runtime su mul/div/%.
   Semantica C99: trunc verso zero, segno resto = segno dividendo. */
#include <stdio.h>

int main(void) {
    /* mul runtime negative */
    int a = 5;
    int b = -3;
    int c = a * b;       /* -15 */
    printf("mul: %d\n", c);

    int d = -7;
    int e = 4;
    int f = d * e;       /* -28 */
    printf("mul: %d\n", f);

    int g = -6;
    int h = -2;
    int i = g * h;       /* 12 */
    printf("mul: %d\n", i);

    /* div/mod runtime negative C99 */
    int x = -10;
    int y = 3;
    printf("div: %d mod: %d\n", x / y, x % y);  /* -3, -1 */

    int x2 = 10;
    int y2 = -3;
    printf("div: %d mod: %d\n", x2 / y2, x2 % y2);  /* -3, 1 */

    int x3 = -10;
    int y3 = -3;
    printf("div: %d mod: %d\n", x3 / y3, x3 % y3);  /* 3, -1 */

    int x4 = 17;
    int y4 = 5;
    printf("div: %d mod: %d\n", x4 / y4, x4 % y4);  /* 3, 2 (positive case still ok) */

    return 0;
}
