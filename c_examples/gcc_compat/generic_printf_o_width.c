/* printf "%No", "%-No", "%0No" runtime via __mn_puto_width / _left / _zero. */
#include <stdio.h>

int main(void) {
    int a = 0xff;        /* 377 octal */
    int b = 0x7;         /* 7 */
    printf("[%5o]\n", a);
    printf("[%5o]\n", b);
    printf("[%-5o]X\n", a);
    printf("[%05o]\n", a);
    printf("[%03o]\n", b);
    return 0;
}
