#include <stdio.h>

typedef struct {
    int a;
    int b;
} item_t;

typedef struct {
    item_t arr[4];
    int n;
} box_t;

box_t B;

int main(void) {
    int i;
    for (i = 0; i < 4; i++) {
        B.arr[i].a = i * 10;
        B.arr[i].b = i * 10 + 1;
    }
    B.n = 4;

    for (i = 0; i < 4; i++) {
        printf("%d %d\n", B.arr[i].a, B.arr[i].b);
    }
    printf("n=%d\n", B.n);
    return 0;
}
