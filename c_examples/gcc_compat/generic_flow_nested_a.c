/* generic_flow_nested_a.c
 * if/while annidati con percorso multiplo.
 */
#include "compat_runtime.h"

int main(void) {
    int i;
    int acc;

    i = 0;
    acc = 0;
    while (i < 5) {
        if (i % 2 == 0) {
            acc = acc + i;
        } else {
            acc = acc + 1;
        }
        i = i + 1;
    }

    printf("%d\n", acc);
    return acc;
}
