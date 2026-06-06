/* `if (c) return E1; return E2;` pattern: pre-pass
   `_transform_early_return_if_then_return` riscrive in single-return.
   Pattern essenziale per molte funzioni con early-exit guard. */
#include <stdio.h>

int max2(int a, int b) {
    if (a > b) return a;
    return b;
}

int abs_v(int x) {
    if (x < 0) return -x;
    return x;
}

int min2(int a, int b) {
    if (a < b) return a;
    return b;
}

int main(void) {
    printf("%d %d %d\n", max2(3, 7), max2(10, 2), max2(5, 5));
    printf("%d %d %d\n", abs_v(-5), abs_v(0), abs_v(7));
    printf("%d %d %d\n", min2(3, 7), min2(10, 2), min2(5, 5));
    return 0;
}
