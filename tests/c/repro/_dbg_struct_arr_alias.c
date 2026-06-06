#include <stdio.h>

typedef struct {
    int a;
    int b;
} item_t;

typedef struct {
    item_t arr[4];
    int cur;
} box_t;

box_t B;

int main(void) {
    int i;
    for (i = 0; i < 4; i++) {
        B.arr[i].a = i * 10;
        B.arr[i].b = i * 10 + 1;
    }
    B.cur = 2;

    item_t* p = &B.arr[B.cur];
    printf("a=%d b=%d\n", p->a, p->b);

    p->a = 99;
    printf("a=%d b=%d\n", p->a, p->b);
    printf("arr2a=%d\n", B.arr[2].a);
    return 0;
}
