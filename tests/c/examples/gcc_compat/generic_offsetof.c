/* offsetof(T, M): Mnemo restituisce field_index * _SIZEOF_SCALAR (=4).
   Mnemo è word-VM senza padding; tutti gli scalari sono 4 byte. */
#include <stdio.h>
#include <stddef.h>

struct Inner { int x; int y; };
struct Outer { int head; struct Inner mid; int tail; };

union U { int a; int b; int c; };

typedef struct { int p; int q; int r; } Pt;

int main(void) {
    int oh = offsetof(struct Outer, head);
    int omx = offsetof(struct Outer, mid.x);
    int omy = offsetof(struct Outer, mid.y);
    int ot = offsetof(struct Outer, tail);
    int ua = offsetof(union U, a);
    int ub = offsetof(union U, b);
    int pq = offsetof(Pt, q);
    int pr = offsetof(Pt, r);
    printf("%d %d %d %d %d %d %d %d\n", oh, omx, omy, ot, ua, ub, pq, pr);
    return oh + omx + omy + ot + ua + ub + pq + pr;
}
