/* generic_runtime_printf_p_b.c
 * printf %p su variabile puntatore da cast intero.
 */
#include "compat_runtime.h"

int main(void) {
    printf("%p\n", (void *)4095);
    return 0;
}
