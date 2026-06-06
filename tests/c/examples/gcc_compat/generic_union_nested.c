#include <stdio.h>

struct Inner { int a; int b; };
union U { struct Inner s; int raw; };
struct Pt { int x; int y; int z; };
union V { struct Pt p; int first; };

int main(void) {
    union U u;
    u.s.a = 100;
    u.s.b = 200;
    printf("%d %d\n", u.s.a, u.s.b);
    printf("%d\n", u.raw);          /* aliases u.s.a */
    u.raw = 42;
    printf("%d %d\n", u.s.a, u.s.b); /* 42 200 */

    union V v;
    v.p.x = 1; v.p.y = 2; v.p.z = 3;
    printf("%d %d %d\n", v.p.x, v.p.y, v.p.z);
    printf("%d\n", v.first);        /* aliases v.p.x */
    return 0;
}
