/* Confronto unsigned a 32 bit con high-bit set (es. 0xFFFFFFFF > 1). Mnemo
   confronta riducendo a magnitudo 32-bit (i valori unsigned sono memorizzati
   sign-extended). Valori a runtime per evitare il const-fold. */
#include <stdio.h>

unsigned id(unsigned x) { return x; }

int main(void) {
    unsigned big = id(0u) - 1u;       /* 0xFFFFFFFF = 4294967295 */
    unsigned hib = id(2147483648u);   /* 0x80000000 */
    unsigned one = id(1u);

    printf("%d %d\n", big < one, big > one);   /* 0 1 */
    printf("%d %d\n", one < big, one > big);   /* 1 0 */
    printf("%d %d\n", hib > one, hib < big);   /* 1 1 */
    printf("%d %d\n", one <= hib, big >= hib); /* 1 1 */

    unsigned s = 0;
    for (unsigned k = 0; k < 5u; k++) s += k;
    printf("s=%u\n", s);               /* 10 */
    return 0;
}
