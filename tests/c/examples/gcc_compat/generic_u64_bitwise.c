/* uint64_t / long long: & | a 64 bit, ritorno da funzione senza maschera a 32 bit. */
#include <stdio.h>
#include <stdint.h>
static uint64_t rotl(uint64_t x, int k) { return (x << k) | (x >> (64 - k)); }
int main(void) {
    long long v[5] = {0x123456789ABCDEF0LL, -1LL, -0x7123456789ABCDEFLL, 0x4000000000000001LL, 77LL};
    for (int i = 0; i < 5; i++) {
        for (int j = 0; j < 5; j++) {
            long long a = v[i], b = v[j];
            printf("%lld %lld\n", a & b, a | b);
        }
    }
    uint64_t u = 0xF0F0F0F0F0F0F0F0ULL;
    uint64_t w = 0x0FF00FF00FF00FF0ULL;
    printf("%llx %llx\n", (unsigned long long)(u & w), (unsigned long long)(u | w));
    int x = -5, y = 12;
    printf("%d %d\n", x & y, x | y);
    printf("%llx\n", (unsigned long long)rotl(0x123456789ABCDEF0ULL, 3));
    return 0;
}
