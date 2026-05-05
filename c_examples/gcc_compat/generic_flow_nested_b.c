/* generic_flow_nested_b.c
 * do-while con switch interno.
 */
#include "compat_runtime.h"

int main(void) {
    int i;
    int out;

    i = 0;
    out = 0;
    do {
        switch (i) {
            case 0:
                out = out + 3;
                break;
            case 1:
                out = out + 5;
                break;
            default:
                out = out + 7;
                break;
        }
        i = i + 1;
    } while (i < 3);

    printf("%d\n", out);
    return out;
}
