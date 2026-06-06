/* I/O stubs: VM no FS/time. Mnemo AST rewrite fflush/feof/time/clock a 0. */
#include <stdio.h>
#include <time.h>

int main(void) {
    printf("a\n");
    fflush(stdout);
    /* feof/ferror su stdout in gcc ritornano 0 inizialmente. Combaciano. */
    if (feof(stdout) == 0) printf("noeof\n");
    if (ferror(stdout) == 0) printf("noerr\n");
    /* clearerr no-op. */
    clearerr(stdout);
    printf("b\n");
    return 0;
}
