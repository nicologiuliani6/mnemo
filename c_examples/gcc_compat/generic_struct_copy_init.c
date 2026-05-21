/* `struct V a = b;` con `b` altra struct stesso tag: copia per-campo.
   Copre anche compound literal `struct V a = (struct V){...}` (hoisted
   in Decl temporanea + ID-ref). */
#include <stdio.h>

struct V { int x; int y; };
typedef struct V V;
struct W { int a; int b; int c; };

int main(void) {
    /* tag diretto */
    struct V b = {3, 4};
    struct V a = b;
    printf("V: %d %d\n", a.x, a.y);

    /* typedef */
    V t = {7, 14};
    V u = t;
    printf("T: %d %d\n", u.x, u.y);

    /* 3 campi */
    struct W w1 = {1, 2, 3};
    struct W w2 = w1;
    printf("W: %d %d %d\n", w2.a, w2.b, w2.c);

    /* compound literal */
    struct V c = (struct V){11, 22};
    printf("CL: %d %d\n", c.x, c.y);

    /* mutazione sorgente non propaga */
    b.x = 99;
    printf("V2: %d %d\n", a.x, a.y);
    return 0;
}
