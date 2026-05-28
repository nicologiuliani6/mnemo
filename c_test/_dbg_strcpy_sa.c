#include <stdio.h>
#include <string.h>

typedef struct {
    int pid;
    char buf[8];
} item_t;

typedef struct {
    item_t arr[3];
} box_t;

box_t B;

int main(void) {
    int i;
    for (i = 0; i < 3; i++) {
        B.arr[i].pid = i + 10;
        strcpy(B.arr[i].buf, "hi");
    }
    printf("p0=%d p1=%d p2=%d\n", B.arr[0].pid, B.arr[1].pid, B.arr[2].pid);
    return 0;
}
