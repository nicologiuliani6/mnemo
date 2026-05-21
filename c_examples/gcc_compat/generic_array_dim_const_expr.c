/* Dimensione array come espressione costante (non solo letterale).
   `_eval_const_int_expr` ora valuta BinaryOp aritmetico, UnaryOp,
   Cast, ternario, comparison su operandi costanti. */
#include <stdio.h>

#define N 4
#define M 3

int main(void) {
    int a[N + 2];          /* 6 */
    int b[2 * 2];          /* 4 */
    int c[N > M ? N : M];  /* 4 */

    for (int i = 0; i < N + 2; i++) a[i] = i + 1;
    int sa = 0;
    for (int i = 0; i < N + 2; i++) sa += a[i];

    for (int i = 0; i < 4; i++) b[i] = 2;
    int sb = 0;
    for (int i = 0; i < 4; i++) sb += b[i];

    for (int i = 0; i < 4; i++) c[i] = i;
    int sc = 0;
    for (int i = 0; i < 4; i++) sc += c[i];

    printf("%d %d %d\n", sa, sb, sc);
    return 0;
}
