/* Nested struct: `struct Outer { struct Inner i; }; o.i.field` */
#include <stdio.h>

struct Inner { int a; int b; };
struct Outer { struct Inner i; int z; };

int main(void) {
    struct Outer o;
    o.i.a = 1;
    o.i.b = 2;
    o.z = 3;
    int s = o.i.a + o.i.b + o.z;
    printf("%d\n", s);
    return s;
}
