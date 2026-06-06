/* fprintf/fputs/fputc su stdout → Mnemo rewrite a printf/putchar.
   stderr → no-op (silente). gcc-compat: stderr scartato dal harness. */
#include <stdio.h>

int main(void) {
    fputs("a", stdout);
    fputs("bc\n", stdout);
    fputc('X', stdout);
    fputc('\n', stdout);
    fprintf(stdout, "%d-%s\n", 7, "ok");
    fprintf(stderr, "ignored\n");
    return 0;
}
