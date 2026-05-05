/* generic_struct_ptr_store.c — Box * locale + bp->v */
#include "compat_runtime.h"

typedef struct {
    int v;
} Box;

int main(void) {
    Box *bp;
    bp = (Box *)malloc(4);
    bp->v = 8;
    printf("%d\n", bp->v);
    free((void *)bp);
    return 0;
}
