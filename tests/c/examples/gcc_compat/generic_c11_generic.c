/* _Generic (C11): pycparser non lo parsa, ma Mnemo lo rewrite a
   compile-time in c_parse.py prima del parsing. Seleziona la prima
   clausola con tipo int-family-supportato (o default se nessuna). */
#include <stdio.h>

#define cat(x) _Generic((x), \
    int: "i", \
    unsigned: "u", \
    char: "c", \
    default: "?")

int main(void) {
    int a = 5;
    unsigned u = 7u;
    char ch = 'A';
    int v1 = _Generic((a), int: 10, default: 0);
    int v2 = _Generic((u), unsigned: 20, default: 0);
    int v3 = _Generic((ch), char: 30, default: 0);
    int v4 = _Generic((a), float: 99, default: 40);
    printf("%d %d %d %d\n", v1, v2, v3, v4);
    return 0;
}
