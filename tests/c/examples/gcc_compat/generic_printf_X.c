/* printf %X / %llX: hex uppercase, compile-time const only. */
#include <stdio.h>

int main(void) {
    printf("%X\n", 255);
    printf("%X\n", 0xdeadbeef);
    printf("%llX\n", 0xCAFEBABEDEADBEEFULL);
    printf("%08X\n", 0xAB);
    printf("%X-%X\n", 0, 16);
    return 0;
}
