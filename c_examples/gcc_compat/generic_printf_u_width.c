/* printf "%Nu", "%-Nu", "%0Nu" runtime via __mn_putd_uint_width / _left / _zero. */
#include <stdio.h>

int main(void) {
    unsigned a = 7u;
    unsigned b = 123u;
    unsigned c = 99u;
    printf("[%5u]\n", a);
    printf("[%5u]\n", b);
    printf("[%5u]\n", c);
    printf("[%-5u]X\n", a);
    printf("[%-3u]X\n", c);
    printf("[%05u]\n", a);
    printf("[%05u]\n", b);
    printf("[%03u]\n", b);
    return 0;
}
