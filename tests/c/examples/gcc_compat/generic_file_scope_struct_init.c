/* File-scope struct con InitList: campi inizializzati al partire del programma.
   Mnemo applica via IAddEq nel pre-instrs di main. */
#include <stdio.h>

struct P { int a; int b; int c; };
struct P pt = {7, 8, 9};
struct P pt_named = {.b = 20, .a = 10};

int main(void) {
    printf("%d %d %d %d %d\n", pt.a, pt.b, pt.c, pt_named.a, pt_named.b);
    pt.a = 100;
    pt.b *= 2;
    printf("%d %d\n", pt.a, pt.b);
    return pt.a + pt.b + pt.c + pt_named.a + pt_named.b;
}
