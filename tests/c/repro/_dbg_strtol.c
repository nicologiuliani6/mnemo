#include <stdio.h>
#include <stdlib.h>

int main(void) {
    printf("%ld\n", strtol("42", (char **)0, 10));
    printf("%ld\n", strtol("-100", (char **)0, 10));
    printf("%ld\n", strtol("0xDEAD", (char **)0, 16));
    printf("%ld\n", strtol("755", (char **)0, 8));
    printf("%ld\n", strtol("101010", (char **)0, 2));
    printf("%ld\n", strtol("0x1F", (char **)0, 0));
    printf("%ld\n", strtol("017", (char **)0, 0));
    printf("%lu\n", strtoul("4000000000", (char **)0, 10));
    return 0;
}
