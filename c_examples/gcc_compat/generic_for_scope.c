/* C99: `for (int i = …; …; …)` ha scope locale. Due loop con stesso
   nome contatore non devono collidere. */
#include <stdio.h>

int main(void) {
    int s = 0;
    for (int i = 0; i < 3; i++) s += i;        /* 0+1+2 = 3 */
    for (int i = 0; i < 5; i++) s += i;        /* 3+0+1+2+3+4 = 13 */
    for (int j = 0; j < 4; j++) {
        for (int j = 10; j < 12; j++) s += j;  /* j inner shadowing */
    }
    printf("%d\n", s);
    return s;
}
