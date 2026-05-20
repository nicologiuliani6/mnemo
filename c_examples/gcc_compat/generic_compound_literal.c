/* CompoundLiteral `(int[]){...}` come argomento. Mnemo lo hoista a Decl sintetico. */
#include <stdio.h>

int sum3(int *a) {
    return a[0] + a[1] + a[2];
}

int main(void) {
    int r = sum3((int[]){1, 2, 3});
    int s = ((int[]){10, 20, 30})[1] + ((int[]){4, 5, 6})[2];
    printf("%d %d\n", r, s);
    return r + s;
}
