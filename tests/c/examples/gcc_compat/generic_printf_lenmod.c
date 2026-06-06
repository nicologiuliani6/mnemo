/* Length modifiers in printf: `l`, `ll`, `h`, `hh`, `z`, `j`, `t`.
   Mnemo è word-VM: tutti gli scalari sono 32-bit, quindi i modifier
   sono no-op. Solo l'output deve coincidere con gcc. */
#include <stdio.h>

int main(void) {
    int x = 42;
    unsigned u = 7;
    printf("%ld %lu %lx\n", (long)x, (unsigned long)u, (unsigned long)x);
    printf("%hd %hu %hx\n", (short)x, (unsigned short)u, (unsigned short)x);
    printf("%hhd %hhu %hhx\n", (signed char)x, (unsigned char)u, (unsigned char)x);
    return x;
}
