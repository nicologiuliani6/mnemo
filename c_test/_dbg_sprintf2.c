#include <stdio.h>

int main(void) {
    char buf[16];
    sprintf(buf, "abc");
    printf("buf=%s\n", buf);
    return 0;
}
