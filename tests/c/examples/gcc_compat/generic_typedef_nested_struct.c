/* Nested struct con typedef: typedef struct {...} T → uso in altra struct */
#include <stdio.h>

typedef struct { int x; int y; } Pt;
typedef struct { Pt tl; Pt br; } Rect;

int main(void) {
    Rect r = {{1, 2}, {5, 7}};
    int area = (r.br.x - r.tl.x) * (r.br.y - r.tl.y);
    printf("%d\n", area);
    return area;
}
