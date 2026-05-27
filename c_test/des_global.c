#include <stdio.h>

typedef unsigned long long u64;
typedef unsigned int u32;

#define M32 0xFFFFFFFFULL

u32 g_sub[16];

u32 F(u32 x, u32 k) {
    x ^= k; x &= M32;
    x = ((x << 3) | (x >> 29)); x &= M32;
    x ^= ((x << 7) | (x >> 25)); x &= M32;
    x += 0x9E3779B9; x &= M32;
    x ^= (x >> 16); x &= M32;
    x *= 0x85EBCA6B; x &= M32;
    x ^= (x >> 13); x &= M32;
    return x;
}

void keyschedule(u64 key) {
    int i;
    for(i = 0; i < 16; i++) {
        key = (key << 5) | (key >> (64 - 5));
        key ^= (0x9E3779B97F4A7C15ULL + i);
        g_sub[i] = (u32)(key & 0xFFFFFFFF);
    }
}

u64 encrypt(u64 block, u64 key) {
    u32 L, R, tmp;
    int i;

    keyschedule(key);

    L = (u32)(block >> 32);
    R = (u32)(block & 0xFFFFFFFF);

    for(i = 0; i < 16; i++) {
        tmp = R;
        R = L ^ F(R, g_sub[i]);
        R &= M32;
        L = tmp;
    }

    return ((u64)L << 32) | R;
}

u64 decrypt(u64 block, u64 key) {
    u32 L, R, tmp;
    int i;

    keyschedule(key);

    L = (u32)(block >> 32);
    R = (u32)(block & 0xFFFFFFFF);

    for(i = 15; i >= 0; i--) {
        tmp = L;
        L = R ^ F(L, g_sub[i]);
        L &= M32;
        R = tmp;
    }

    return ((u64)L << 32) | R;
}

int main(void) {
    u64 plain  = 0x123456789ABCDEF0ULL;
    u64 key    = 0x0F1E2D3C4B5A6978ULL;
    u64 cipher = encrypt(plain, key);
    u64 dec    = decrypt(cipher, key);
    printf("plain : %llx\n", plain);
    printf("cipher: %llx\n", cipher);
    printf("dec   : %llx\n", dec);
    return 0;
}
