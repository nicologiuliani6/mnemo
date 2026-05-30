#include <stdio.h>
#include <time.h>

int main(void) {
    printf("before flush\n");
    fflush(stdout);
    if (feof(stdout) == 0) printf("no eof\n");
    time_t t = time((time_t *)0);
    if (t == 0) printf("time=0\n");
    return 0;
}
