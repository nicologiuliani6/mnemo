/* sprintf/snprintf compile-time fmt parsing. */
#include <stdio.h>

int main(void) {
    char buf[64];
    sprintf(buf, "hello %d %s", 42, "world");
    printf("buf=%s\n", buf);

    char buf2[16];
    snprintf(buf2, 12, "%d-%d", 12345, 67);
    printf("buf2=%s\n", buf2);

    char buf3[16];
    sprintf(buf3, "x=%x", 0xDEADBE);
    printf("buf3=%s\n", buf3);

    return 0;
}
