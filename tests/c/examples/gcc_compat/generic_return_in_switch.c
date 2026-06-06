/* return dentro case/default di una funzione con body switch-only.
   Pre-pass `_transform_switch_returns` in compile.py riscrive in
   single-return: `__mn_rv = V; break;` + `return __mn_rv;`. */
#include <stdio.h>

int classify(int x) {
    switch (x) {
        case 0: return 100;
        case 1: return 200;
        case 2: return 300;
        default: return 999;
    }
}

int sign(int x) {
    switch (x < 0 ? 0 : (x > 0 ? 2 : 1)) {
        case 0: return -1;
        case 1: return 0;
        case 2: return 1;
        default: return 42;
    }
}

int main(void) {
    printf("%d\n", classify(0));
    printf("%d\n", classify(1));
    printf("%d\n", classify(2));
    printf("%d\n", classify(5));
    printf("%d\n", sign(-7));
    printf("%d\n", sign(0));
    printf("%d\n", sign(8));
    return 0;
}
