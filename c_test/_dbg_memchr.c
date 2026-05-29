#include <stdio.h>
#include <string.h>

int main(void) {
    const char *a = memchr("hello", 'l', 5);
    const char *b = memchr("hello", 'z', 5);
    const char *c = memchr("hello", 'h', 1);
    const char *d = memchr("hello", 'e', 1);  /* not found in 1 byte */

    if (a) printf("a=%s\n", a); else printf("a=NULL\n");
    if (b) printf("b=%s\n", b); else printf("b=NULL\n");
    if (c) printf("c=%s\n", c); else printf("c=NULL\n");
    if (d) printf("d=%s\n", d); else printf("d=NULL\n");
    return 0;
}
