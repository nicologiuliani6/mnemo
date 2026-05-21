/* `struct V t = *p;` — inizializzazione struct via deref di struct-ptr.
   Espande in `t.f = p->f` per ogni campo della struct. */
#include <stdio.h>

struct V { int x; int y; };
typedef struct V V;
struct W { int a; int b; int c; int d; };

int main(void) {
    /* tag diretto */
    struct V s1 = {3, 9};
    struct V *p1 = &s1;
    struct V t1 = *p1;
    printf("V: %d %d\n", t1.x, t1.y);

    /* typedef */
    V s2 = {11, 22};
    V *p2 = &s2;
    V t2 = *p2;
    printf("T: %d %d\n", t2.x, t2.y);

    /* 4 campi */
    struct W s3 = {1, 2, 3, 4};
    struct W *p3 = &s3;
    struct W t3 = *p3;
    printf("W: %d %d %d %d\n", t3.a, t3.b, t3.c, t3.d);

    /* copy-by-value: mutazione sorgente non propaga a destinatario */
    s1.x = 999;
    printf("V2: %d %d\n", t1.x, t1.y);
    return 0;
}
