/* generic_char_printf_mix.c
 * Mix di %%, %c e %d in stampa.
 */
#include "compat_runtime.h"

int main(void) {
    int c1;
    int c2;
    int n;

    c1 = 79; /* O */
    c2 = 75; /* K */
    n = 2026;

    printf("%% %c%c %d\n", c1, c2, n);
    return 6;
}
