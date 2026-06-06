/* Enum const usate come dimensione array. `_eval_const_int_expr`
   risolve `c.ID(name)` via `ctx.enum_constants[name]` quando ctx
   è disponibile. */
#include <stdio.h>

enum { N = 4, M = 3, K = N + M };

int main(void) {
    int a[N];
    int b[M * 2];
    int c[K];                  /* 7 */
    int d[N > M ? N : M];      /* 4 */

    for (int i = 0; i < N; i++) a[i] = i;
    int sa = 0;
    for (int i = 0; i < N; i++) sa += a[i];

    for (int i = 0; i < M * 2; i++) b[i] = 1;
    int sb = 0;
    for (int i = 0; i < M * 2; i++) sb += b[i];

    for (int i = 0; i < K; i++) c[i] = 2;
    int sc = 0;
    for (int i = 0; i < K; i++) sc += c[i];

    for (int i = 0; i < N; i++) d[i] = i + 1;
    int sd = 0;
    for (int i = 0; i < N; i++) sd += d[i];

    printf("%d %d %d %d\n", sa, sb, sc, sd);
    return 0;
}
