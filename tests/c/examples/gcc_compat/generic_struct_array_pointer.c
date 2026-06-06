#include <stdio.h>

struct P { int x; int y; };

int main(void) {
    struct P a[3];
    a[0].x = 1; a[0].y = 2;
    a[1].x = 3; a[1].y = 4;
    a[2].x = 5; a[2].y = 6;

    struct P *p = a;            /* array decay = &a[0] */
    printf("%d %d\n", p->x, p->y);
    p++;                        /* stride = sizeof(struct P) */
    printf("%d %d\n", p->x, p->y);

    struct P *q = &a[2];        /* address of element (const index) */
    printf("%d %d\n", q->x, q->y);

    int i = 1;
    struct P *r = &a[i];        /* runtime index */
    printf("%d %d\n", r->x, r->y);

    struct P *s = p + 1;        /* pointer + int (scaled) */
    printf("%d %d\n", s->x, s->y);

    p->x = 30;                  /* write through struct pointer */
    printf("%d\n", a[1].x);
    return 0;
}
