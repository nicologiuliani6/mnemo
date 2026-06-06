/* Nested struct init: `struct Rect r = {{x,y},{x,y}}` */
#include <stdio.h>

struct Pt   { int x; int y; };
struct Rect { struct Pt tl; struct Pt br; };

int main(void) {
    struct Rect a = {{1, 2}, {5, 7}};
    struct Rect b = {{10, 20}, {30, 40}};
    int area_a = (a.br.x - a.tl.x) * (a.br.y - a.tl.y);
    int sum_b  = b.tl.x + b.tl.y + b.br.x + b.br.y;
    printf("%d %d\n", area_a, sum_b);
    return area_a + sum_b;
}
