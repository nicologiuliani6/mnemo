/* perror(s) → stampa "s: errstr\n" su stderr.
   Mnemo: stderr no-op. gcc-compat ignora stderr. */
#include <stdio.h>

int main(void) {
    printf("before\n");
    perror("anything");
    printf("middle\n");
    perror("ignored too");
    printf("after\n");
    return 0;
}
