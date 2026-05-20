/* static int n; persiste tra chiamate (semantica gcc). Mnemo hoista a file-scope. */
#include <stdio.h>

int counter(void) {
    static int n = 0;
    n += 1;
    return n;
}

int summer(int x) {
    static int total = 100;
    total += x;
    return total;
}

int main(void) {
    int a = counter();   /* 1 */
    int b = counter();   /* 2 */
    int c = counter();   /* 3 */
    int d = summer(5);   /* 105 */
    int e = summer(10);  /* 115 */
    printf("%d %d %d %d %d\n", a, b, c, d, e);
    return a + b + c + d + e;
}
