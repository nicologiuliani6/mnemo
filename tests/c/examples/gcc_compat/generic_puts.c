/* puts(s) — emette stringa + '\n'. Mnemo: lowered come printf. */
#include <stdio.h>

int main(void) {
    puts("hello");
    char *s = "world";
    puts(s);
    return 0;
}
