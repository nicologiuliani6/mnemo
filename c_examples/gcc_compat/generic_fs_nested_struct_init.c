/* File-scope struct con InitList nidificata: `{1, {42}, 99}`. */
#include <stdio.h>

struct Inner { int v; int w; };
struct Outer { int hdr; struct Inner inner; int tail; };

struct Outer g = {1, {42, 84}, 99};

int main(void) {
    printf("%d %d %d %d\n", g.hdr, g.inner.v, g.inner.w, g.tail);
    g.inner.v = 1000;
    printf("%d\n", g.inner.v);
    return g.hdr + g.inner.v + g.inner.w + g.tail;
}
