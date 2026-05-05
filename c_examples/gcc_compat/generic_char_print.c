/* generic_char_print.c
 * Stampa caratteri usando %c con codici interi.
 */
#include "compat_runtime.h"

int main(void) {
    int a;
    int b;
    int c;
    int code_sum;

    a = 65; /* A */
    b = 90; /* Z */
    c = 33; /* ! */
    code_sum = a + b + c;

    printf("%c%c%c\n", a, b, c);
    printf("%d\n", code_sum);
    return code_sum % 10;
}
