/* errno: lettura supportata, sempre 0 (no syscall fail). E* costanti. */
#include <stdio.h>
#include <errno.h>

int main(void) {
    printf("errno=%d\n", errno);
    printf("EINVAL=%d\n", EINVAL);
    printf("ENOMEM=%d\n", ENOMEM);
    return 0;
}
