#include <stdio.h>

typedef unsigned int u32;

void fill(int k, u32 a[4]) {
    int i;
    for (i = 0; i < 4; i++) a[i] = i + 100 + k;
}

void use(void) {
    u32 a[4] = {0};
    fill(0, a);
    int i;
    for (i = 0; i < 4; i++) printf("%u\n", a[i]);
}

int main(void) {
    use();
    return 0;
}
