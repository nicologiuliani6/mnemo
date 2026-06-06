/* Designated initializer per struct: `struct P p = {.x=1, .y=2}` */
#include <stdio.h>

struct P { int x; int y; int z; };

int main(void) {
    struct P p = {.x=1, .y=2, .z=3};
    struct P q = {.z=30, .x=10};
    struct P r = {100, .z=300};
    int s = p.x + p.y + p.z + q.x + q.y + q.z + r.x + r.y + r.z;
    printf("%d\n", s);
    return s;
}
