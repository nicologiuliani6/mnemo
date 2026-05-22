/* printf "%-Nd" e "%0Nd" runtime: __mn_putd_width_left e __mn_putd_width_zero.
   %-: digit chars poi padding spazi. %0: padding zeri (dopo segno se n<0). */
#include <stdio.h>

int main(void) {
    int a = 7;
    int b = 123;
    int c = -5;
    /* left align */
    printf("[%-5d]X\n", a);
    printf("[%-5d]X\n", b);
    printf("[%-5d]X\n", c);
    printf("[%-3d]X\n", b);
    /* zero pad */
    printf("[%05d]\n", a);
    printf("[%05d]\n", b);
    printf("[%05d]\n", c);
    printf("[%03d]\n", b);
    printf("[%02d]\n", c);
    return 0;
}
