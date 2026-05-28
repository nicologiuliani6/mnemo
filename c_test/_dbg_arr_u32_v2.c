#include <stdio.h>

typedef unsigned int u32;
typedef unsigned long long u64;

void fill(u64 k, u32 a[4]) {
    int i;
    for (i = 0; i < 4; i++) a[i] = i + 100;
}

void use(u64 key) {
    u32 a[4] = {0};
    fill(key, a);
    int i;
    for (i = 0; i < 4; i++) printf("%u\n", a[i]);
}

int main(void) {
    use(0x0F1E2D3C4B5A6978ULL);
    return 0;
}
