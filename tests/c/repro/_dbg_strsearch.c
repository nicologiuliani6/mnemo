#include <stdio.h>
#include <string.h>

int main(void) {
    const char *a = strchr("hello", 'l');
    const char *b = strrchr("hello", 'l');
    const char *c = strchr("hello", 'z');
    const char *d = strstr("hello world", "world");
    const char *e = strstr("hello world", "xyz");
    const char *f = strpbrk("hello", "aeiou");
    const char *g = strpbrk("xyz", "aeiou");

    if (a) printf("a=%s\n", a); else printf("a=NULL\n");
    if (b) printf("b=%s\n", b); else printf("b=NULL\n");
    if (c) printf("c=%s\n", c); else printf("c=NULL\n");
    if (d) printf("d=%s\n", d); else printf("d=NULL\n");
    if (e) printf("e=%s\n", e); else printf("e=NULL\n");
    if (f) printf("f=%s\n", f); else printf("f=NULL\n");
    if (g) printf("g=%s\n", g); else printf("g=NULL\n");

    return 0;
}
