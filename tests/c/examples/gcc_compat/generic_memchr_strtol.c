/* memchr + strtol + atol + atoll compile-time. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int main(void) {
    const char *p = memchr("hello", 'l', 5);
    if (p) printf("p=%s\n", p);

    printf("%ld\n", strtol("42", (char **)0, 10));
    printf("%ld\n", strtol("0xDEAD", (char **)0, 16));
    printf("%ld\n", strtol("0x1F", (char **)0, 0));
    printf("%lu\n", strtoul("4000000000", (char **)0, 10));

    printf("%ld\n", atol("-100"));
    printf("%lld\n", atoll("123456789"));

    return 0;
}
