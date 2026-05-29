#include <stdio.h>
#include <inttypes.h>

int main(void) {
    int32_t a = 42;
    int64_t b = 100;
    uint32_t c = 0xDEADBEEF;
    uint64_t d = 0xFEEDFACE12345678ULL;

    printf("%" PRId32 "\n", a);
    printf("%" PRId64 "\n", b);
    printf("%" PRIx32 "\n", c);
    printf("%" PRIx64 "\n", d);

    return 0;
}
