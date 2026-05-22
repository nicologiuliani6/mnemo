/* printf "%Nd" con argomento runtime: __mn_putd_width emette padding
   spazi a sinistra (`width - digits - (segno?)`) e poi __mn_putd(n). */
#include <stdio.h>

int main(void) {
    int a = 7;
    int b = 123;
    int c = -5;
    int d = 0;
    printf("[%5d]\n", a);
    printf("[%5d]\n", b);
    printf("[%5d]\n", c);
    printf("[%3d]\n", b);
    printf("[%1d]\n", b);
    printf("[%4d]\n", d);
    return 0;
}
