#include <stdio.h>

typedef unsigned int u32;
typedef unsigned long long u64;

void fill(u64 k, u32 a[4]) {
    int i;
    for (i = 0; i < 4; i++) {
        k = (k << 5) | (k >> 59);
        k ^= 0x9E3779B9ULL + i;
        a[i] = (u32)(k & 0xFFFFFFFF);
    }
}

void use(u64 key) {
    u32 a[4] = {0};
    fill(key, a);
    int i;
    for (i = 0; i < 4; i++) printf("%x\n", a[i]);
}

int main(void) {
    use(0x0F1E2D3C4B5A6978ULL);
    return 0;
}
