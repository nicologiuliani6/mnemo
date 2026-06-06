/* generic_runtime_printf_x_b.c
 * printf %x su espressione costante.
 */
#include "compat_runtime.h"

int main(void) {
    int x;
    x = 26;
    printf("%x\n", x);
    return 0;
}
