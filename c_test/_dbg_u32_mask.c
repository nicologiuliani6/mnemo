#include <stdio.h>

typedef unsigned int u32;

int main(void) {
    u32 x = 0xFF000000u;
    u32 y;
    y = (x << 3) | (x >> 29);
    printf("y=%x\n", y);
    x += 0x9E3779B9u;
    printf("x=%x\n", x);
    return 0;
}
