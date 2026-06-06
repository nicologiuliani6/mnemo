/* exit(N) dentro main → return N. AST rewrite Mnemo. */
// mnemo-main-argc: 1
#include <stdio.h>
#include <stdlib.h>

int main(int argc, char **argv) {
    (void)argv;
    printf("hello\n");
    if (argc == 1) {
        printf("argc==1\n");
        exit(7);
    }
    printf("never\n");
    return 0;
}
