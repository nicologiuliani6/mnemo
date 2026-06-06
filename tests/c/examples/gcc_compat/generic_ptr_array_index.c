/* `p[i]` su puntatore + `(*q)[i]` con pointer-to-array.
   Mnemo rewrite a `*(p+i)` / `*(q+i)` in r-value e l-value. */
#include <stdio.h>

int main(void) {
    int a[4] = {10, 20, 30, 40};
    int *p = a;
    /* p[i] rvalue */
    int s = p[0] + p[1] + p[2] + p[3];

    /* p[i] lvalue */
    p[0] = 100;
    p[3] = 400;

    /* pointer-to-array */
    int (*q)[4] = &a;
    (*q)[1] = 200;
    (*q)[2] = 300;

    printf("%d %d %d %d %d\n", a[0], a[1], a[2], a[3], s);
    return a[0] + a[1] + a[2] + a[3];
}
