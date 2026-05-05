/* generic_struct_fields_b.c
 * Struct con aggiornamenti successivi via accesso diretto.
 */
#include "compat_runtime.h"

typedef struct {
    int a;
    int b;
} Box;

int main(void) {
    Box first;
    Box second;
    int out;

    first.a = 4;
    first.b = 9;
    second.a = first.a + 6;
    second.b = first.b - 2;

    out = second.a * second.b;
    printf("%d\n", out);
    return out / 10;
}
