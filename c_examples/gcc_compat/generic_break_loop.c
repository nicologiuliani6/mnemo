/* break in loop deve interrompere il body, non solo skippare iter successive. */
#include <stdio.h>

int main(void) {
    int s = 0;
    for (int i = 0; i < 100; i += 1) {
        if (i == 5) break;
        s += i;
    }
    int t = 0;
    int j = 0;
    while (j < 100) {
        if (j == 7) break;
        t += j;
        j += 1;
    }
    printf("%d %d\n", s, t);
    return s + t * 100;
}
