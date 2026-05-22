/* printf "%Nx", "%-Nx", "%0Nx" runtime via __mn_putx_width / _left / _zero.
   Helper __mn_hcount_unsigned conta cifre hex. */
#include <stdio.h>

int main(void) {
    int a = 0xab;
    int b = 0x1f;
    int c = 0x7;
    printf("[%5x]\n", a);
    printf("[%5x]\n", b);
    printf("[%5x]\n", c);
    printf("[%-5x]X\n", a);
    printf("[%-3x]X\n", c);
    printf("[%05x]\n", a);
    printf("[%05x]\n", c);
    printf("[%03x]\n", b);
    return 0;
}
