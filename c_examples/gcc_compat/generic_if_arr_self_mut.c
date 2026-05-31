/* generic_if_arr_self_mut.c
 * Regression: `if (arr[k] == c) arr[k] = v` con k costante.
 * Pre-fix Mnemo: IF/FI non reversibile (FI guard fallisce post-body).
 * Fix: _transform_hoist_unsafe_if_conds rileva ArrayRef base ID.
 */
#include "compat_runtime.h"

int G[3];

void touch_idx0(void) {
    if (G[0] == 0) {
        G[0] = 1;
    }
}

void touch_idx_loop(void) {
    int i;
    for (i = 0; i < 3; i++) {
        if (G[i] == 0) {
            G[i] = i + 10;
        }
    }
}

int main(void) {
    G[0] = 0; G[1] = 0; G[2] = 0;
    touch_idx0();
    touch_idx_loop();
    printf("%d %d %d\n", G[0], G[1], G[2]);
    return 0;
}
