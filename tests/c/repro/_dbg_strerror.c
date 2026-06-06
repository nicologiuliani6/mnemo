#include <stdio.h>
#include <string.h>
#include <errno.h>

int main(void) {
    printf("0: %s\n", strerror(0));
    printf("EINVAL: %s\n", strerror(EINVAL));
    printf("ENOMEM: %s\n", strerror(ENOMEM));
    printf("ENOENT: %s\n", strerror(ENOENT));
    return 0;
}
