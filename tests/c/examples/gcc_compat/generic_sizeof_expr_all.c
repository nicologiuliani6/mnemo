/* sizeof su tutti i tipi di espressione: aritmetica, cast, ternario,
   funccall, letterali. */
#include <stdio.h>

int f(void) { return 42; }

int main(void) {
    int a = sizeof(1 + 2 * 3);      /* sizeof(int)=4 */
    int b = sizeof((char)42);       /* sizeof(int)=4 dopo cast */
    int c = sizeof(1 > 0 ? 1 : 2);  /* sizeof(int)=4 */
    int d = sizeof(f());            /* sizeof(int)=4 */
    int e = sizeof('A');            /* gcc: sizeof(int)=4 */
    int g = sizeof("hi");           /* len+1 = 3 */
    int h = sizeof("hello");        /* 6 */
    printf("%d %d %d %d %d %d %d\n", a, b, c, d, e, g, h);
    return a + b + c + d + e + g + h;
}
