#define _POSIX_C_SOURCE 200809L
#include <stdio.h>
#include <string.h>

int main(void) {
    printf("%lu\n", (unsigned long)strnlen("hello", 100));
    printf("%lu\n", (unsigned long)strnlen("hello", 3));
    printf("%lu\n", (unsigned long)strnlen("hello", 5));
    printf("%lu\n", (unsigned long)strnlen("", 10));
    return 0;
}
