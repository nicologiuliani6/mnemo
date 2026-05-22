/* return in if/else-if/else chain (function body is single If con else).
   Pre-pass `_transform_if_chain_returns` riscrive in single-return tramite
   var `__mn_rv2`. */
#include <stdio.h>

int sign(int x) {
    if (x < 0) return -1;
    else if (x > 0) return 1;
    else return 0;
}

int clamp(int x) {
    if (x < 0) return 0;
    else if (x > 100) return 100;
    else return x;
}

int main(void) {
    printf("%d %d %d\n", sign(-5), sign(0), sign(7));
    printf("%d %d %d\n", clamp(-3), clamp(50), clamp(200));
    return 0;
}
