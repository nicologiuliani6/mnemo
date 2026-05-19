/* generic_void_pointer.c
 * void* + cast (int*)void_ptr lowered come pool slot int.
 */
#include "compat_runtime.h"

int main(void) {
    int x;
    void *p;
    int *q;
    int r;

    x = 42;
    p = &x;
    q = (int *)p;
    r = *q;

    printf("%d\n", r);
    return r;
}
