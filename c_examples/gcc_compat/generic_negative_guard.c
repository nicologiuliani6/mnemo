/* Guard con letterale negativo: `if x > -5 then` */
#include <stdio.h>

int main(void) {
    int x = 3;
    int r = 0;
    if (x > -5) r = 100;
    if (x < -1) r += 1;
    int i = 0;
    while (i > -3) { r += 1; i -= 1; }
    printf("%d\n", r);
    return r;
}
