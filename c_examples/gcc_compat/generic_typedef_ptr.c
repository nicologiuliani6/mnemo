/* `typedef int *IntPtr; IntPtr p = &x;` — typedef-of-pointer
   risolto a livello di Decl. */
#include <stdio.h>

typedef int *IntPtr;
typedef char *CharPtr;
typedef unsigned *UIntPtr;

int main(void) {
    int a = 10;
    char c = 'X';
    unsigned u = 42u;

    IntPtr p = &a;
    CharPtr cp = &c;
    UIntPtr up = &u;

    *p = 100;
    *cp = 'Y';
    *up = 999;

    printf("%d %c %u\n", a, c, u);
    return a + (int)c + (int)u;
}
