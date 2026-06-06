#include <stdio.h>

typedef unsigned long long u64;
typedef unsigned int u32;

u32 F(u32 x, u32 k) {
    x ^= k;

    x = ((x << 3) | (x >> 29));
    x ^= ((x << 7) | (x >> 25));
    x += 0x9E3779B9;

    x ^= (x >> 16);
    x *= 0x85EBCA6B;
    x ^= (x >> 13);

    return x;
}

void keyschedule(u64 key, u32 subkeys[16]) {
    int i;

    for(i = 0; i < 16; i++) {
        key =
            (key << 5) |
            (key >> (64 - 5));

        key ^= (0x9E3779B97F4A7C15ULL + i);

        subkeys[i] = (u32)(key & 0xFFFFFFFF);
    }
}

u64 encrypt(u64 block, u64 key) {
    u32 L, R, tmp;
    u32 subkeys[16];
    int i;

    keyschedule(key, subkeys);

    L = (u32)(block >> 32);
    R = (u32)(block & 0xFFFFFFFF);

    for(i = 0; i < 16; i++) {
        tmp = R;
        R = L ^ F(R, subkeys[i]);
        L = tmp;
    }

    return ((u64)L << 32) | R;
}

u64 decrypt(u64 block, u64 key) {
    u32 L, R, tmp;
    u32 subkeys[16];
    int i;

    keyschedule(key, subkeys);

    L = (u32)(block >> 32);
    R = (u32)(block & 0xFFFFFFFF);

    for(i = 15; i >= 0; i--) {
        tmp = L;
        L = R ^ F(L, subkeys[i]);
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