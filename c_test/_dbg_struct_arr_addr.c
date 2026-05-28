#include <stdio.h>

typedef struct {
    int a;
    int b;
} item_t;

typedef struct {
    item_t arr[3];
    int n;
} box_t;

box_t B;

int main(void) {
    B.arr[0].a = 10;
    B.arr[0].b = 20;
    B.arr[1].a = 30;
    B.arr[1].b = 40;
    B.n = 2;

    int slot1 = (int)(long)&B.arr[1];
    int slot0 = (int)(long)&B.arr[0];
    printf("a1=%d b1=%d n=%d diff=%d\n", B.arr[1].a, B.arr[1].b, B.n, slot1 - slot0);
    return 0;
}
