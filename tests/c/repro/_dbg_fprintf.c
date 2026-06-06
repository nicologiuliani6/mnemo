#include <stdio.h>

int main(void) {
    fputs("hello ", stdout);
    fputc('!', stdout);
    fputc('\n', stdout);
    fprintf(stdout, "x=%d\n", 42);
    fprintf(stderr, "silent\n");
    return 0;
}
