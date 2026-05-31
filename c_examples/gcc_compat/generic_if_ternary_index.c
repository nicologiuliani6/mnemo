/* generic_if_ternary_index.c
 * Regression: ternary dentro array-index in una cond che viene hoisted,
 * con self-mut nel body. `if (g[k>0?1:0]==0) g[k>0?1:0]=v`.
 * Il ternary genera un IF interno con push/pop su __mn_hist; combinato con
 * opt-uncall l'inverse non bilanciava (POP sotto pavimento). Fix: fn con
 * cond-hoisted contenente TernaryOp escluse da opt-uncall (compile.py).
 */
#include "compat_runtime.h"

int g[2];

void set_branch(int k) {
    if (g[k > 0 ? 1 : 0] == 0) {
        g[k > 0 ? 1 : 0] = 7;
    }
}

int main(void) {
    g[0] = 0;
    g[1] = 0;
    set_branch(1);
    set_branch(-1);
    printf("%d %d\n", g[0], g[1]);
    return 0;
}
