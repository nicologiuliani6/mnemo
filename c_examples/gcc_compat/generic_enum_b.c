/* generic_enum_b.c
 * Enum con aritmetica semplice su valori.
 */
#include "compat_runtime.h"

enum Step {
    STEP_A = 3,
    STEP_B = 5
};

int main(void) {
    enum Step s;
    int out;

    s = STEP_A;
    out = s + STEP_B;
    printf("%d\n", out);
    return out;
}
