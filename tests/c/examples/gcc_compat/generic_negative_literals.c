/* Letterali negativi: `r = -1; a -= -3; if (x<0)` */
#include <stdio.h>

int main(void) {
    int a = -5;
    int b = a + 10;
    a -= -3;
    int x = -3;
    int r = 0;
    if (x < 0) r = 100;
    while (x < 0) { x += 1; r += 1; }
    printf("%d %d %d\n", a, b, r);
    return b + a + r;
}
