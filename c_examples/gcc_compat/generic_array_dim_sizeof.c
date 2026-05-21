/* `int arr[sizeof(T)]` o `int arr[sizeof(T) * N]`: `_eval_const_int_expr`
   ora accetta `sizeof(Typename)` quando ha accesso a `ctx`. */
#include <stdio.h>

struct V { int x; int y; int z; };

int main(void) {
    /* sizeof(int) = 4 in mnemo (word-VM, _SIZEOF_SCALAR = 4) */
    int a[sizeof(int)];          /* dim = 4 */
    int b[sizeof(int) * 2];      /* dim = 8 */
    int c[sizeof(struct V)];     /* dim = 12 (3 campi int * 4) */

    for (int i = 0; i < (int)sizeof(int); i++) a[i] = i;
    int sa = 0;
    for (int i = 0; i < (int)sizeof(int); i++) sa += a[i];

    for (int i = 0; i < (int)(sizeof(int) * 2); i++) b[i] = 1;
    int sb = 0;
    for (int i = 0; i < (int)(sizeof(int) * 2); i++) sb += b[i];

    for (int i = 0; i < (int)sizeof(struct V); i++) c[i] = 2;
    int sc = 0;
    for (int i = 0; i < (int)sizeof(struct V); i++) sc += c[i];

    printf("%d %d %d\n", sa, sb, sc);
    return 0;
}
