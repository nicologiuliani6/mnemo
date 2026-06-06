/* Assegnamento struct come statement: `b = a;` o `b = *p;`.
   Espande in copia per-campo. */
#include <stdio.h>

struct V { int x; int y; };
struct W { int a; int b; int c; };

int main(void) {
    struct V v1 = {1, 2};
    struct V v2 = {0, 0};
    v2 = v1;
    printf("V: %d %d\n", v2.x, v2.y);

    /* assegnamento via deref */
    struct V v3 = {0, 0};
    struct V *p = &v1;
    v3 = *p;
    printf("VD: %d %d\n", v3.x, v3.y);

    /* 3 campi */
    struct W w1 = {7, 8, 9};
    struct W w2 = {0, 0, 0};
    w2 = w1;
    printf("W: %d %d %d\n", w2.a, w2.b, w2.c);

    /* re-assegnamento sovrascrive */
    v2 = (struct V){99, 100};
    printf("V2: %d %d\n", v2.x, v2.y);
    return 0;
}
