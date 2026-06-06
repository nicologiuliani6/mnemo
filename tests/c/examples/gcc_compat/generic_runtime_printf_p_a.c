/* generic_runtime_printf_p_a.c
 * printf %p su cast costante non-zero.
 */
#include "compat_runtime.h"

int main(void) {
    printf("%p\n", (void *)26);
    return 0;
}
