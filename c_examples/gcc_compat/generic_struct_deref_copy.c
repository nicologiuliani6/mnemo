/* `*q = *p;` su `struct V *p` / `struct V *q`: espandi in copia
   per-campo (`q->f = p->f` per ogni campo). Supporto sia tag diretto
   (`struct P`) sia via typedef (`typedef struct P P;`). La copia è
   per-valore: mutazioni successive di `*p` non si propagano. */
#include <stdio.h>

struct V { int x; int y; };
typedef struct V V;

struct W { int a; int b; int c; int d; };

int main(void) {
    /* tag diretto */
    struct V v1 = {10, 20};
    struct V v2 = {0, 0};
    struct V *p = &v1;
    struct V *q = &v2;
    *q = *p;
    printf("V: %d %d\n", v2.x, v2.y);

    /* typedef */
    V t1 = {7, 14};
    V t2 = {1, 1};
    V *pt = &t1;
    V *qt = &t2;
    *qt = *pt;
    printf("T: %d %d\n", t2.x, t2.y);

    /* 4 campi */
    struct W w1 = {1, 2, 3, 4};
    struct W w2 = {0, 0, 0, 0};
    struct W *pw = &w1;
    struct W *qw = &w2;
    *qw = *pw;
    printf("W: %d %d %d %d\n", w2.a, w2.b, w2.c, w2.d);

    /* copia per-valore: mutazione sorgente non propaga */
    v1.x = 999;
    printf("V2: %d %d\n", v2.x, v2.y);
    return 0;
}
