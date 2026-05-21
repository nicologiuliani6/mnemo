/* struct S v = f(...); — init di struct da return-by-value di funzione. */
#include <stdio.h>

struct S { int a; int b; int c; };

struct S mk(int x) {
    struct S s = {x, x * 2, x * 3};
    return s;
}

int main(void) {
    struct S r = mk(7);
    printf("%d %d %d\n", r.a, r.b, r.c);
    return r.a + r.b + r.c;
}
