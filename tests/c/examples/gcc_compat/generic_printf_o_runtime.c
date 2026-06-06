/* `printf("%o", val)` con val runtime (variabile o espressione).
   `__mn_puto` definito in `lib/puto.kairos`, analoga a `__mn_putx`
   ma base 8 e senza ramo per digit >= 10. */
#include <stdio.h>

int main(void) {
    int a = 8;
    int b = 64;
    int c = 511;
    int d = a * a;        /* 64 → "100" */
    int e = c + 1;        /* 512 → "1000" */
    printf("%o %o %o %o %o\n", a, b, c, d, e);
    return 0;
}
