/* _Alignof(T): Mnemo restituisce _SIZEOF_SCALAR (4) per qualunque T. */
#include <stdio.h>

typedef struct { int a; int b; } P;

int main(void) {
    int s_int = sizeof(int);
    int a_int = _Alignof(int);
    int a_p = _Alignof(P);
    printf("%d %d %d\n", s_int, a_int, a_p);
    return s_int + a_int + a_p;
}
