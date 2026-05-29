/* strncmp + strnlen compile-time. */
#define _POSIX_C_SOURCE 200809L
#include <stdio.h>
#include <string.h>

int main(void) {
    printf("%d\n", strncmp("hello", "hello", 5));
    printf("%d\n", strncmp("hello", "help", 3));
    printf("%d\n", strncmp("hello", "help", 4));
    printf("%d\n", strncmp("abc", "abcd", 3));

    printf("%lu\n", (unsigned long)strnlen("hello", 100));
    printf("%lu\n", (unsigned long)strnlen("hello", 3));
    printf("%lu\n", (unsigned long)strnlen("", 10));
    return 0;
}
