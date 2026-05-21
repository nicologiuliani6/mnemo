/* `%u` runtime: usa `__mn_putd_uint` (precedentemente passava
   per `__mn_putd` ed era identico a `%d`). Valori unsigned grandi
   ma rappresentabili come int non-negativo. */
#include <stdio.h>

unsigned compute(unsigned a, unsigned b) {
    return a * b;
}

int main(void) {
    unsigned a = 42;
    unsigned b = 100;
    unsigned c = compute(a, b);
    printf("%u %u %u\n", a, b, c);
    printf("%u\n", 4000000000u);
    return (int)c;
}
