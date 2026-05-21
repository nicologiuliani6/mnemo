/* `<ctype.h>`: isdigit/isalpha/isspace/toupper/tolower come
   macro ASCII inline. Output normalizzato a 0/1 perché glibc
   ritorna bitmask non-zero, Mnemo bool 0/1. */
#include <stdio.h>
#include <ctype.h>

int main(void) {
    int a = isdigit('5') != 0;
    int b = isdigit('x') != 0;
    int c = isalpha('z') != 0;
    int d = isalpha('!') != 0;
    int e = isspace(' ') != 0;
    int f = isspace('a') != 0;
    char u = (char)toupper('m');
    char l = (char)tolower('M');
    int isxh = isxdigit('a') != 0;
    int isxn = isxdigit('Z') != 0;
    printf("%d %d %d %d %d %d %c %c %d %d\n", a, b, c, d, e, f, u, l, isxh, isxn);
    return a + c + e;
}
