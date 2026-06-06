/* char* ritornato da funzione + printf("%s", f(...)) (arg FuncCall) e
   assegnazione `const char *s = f(...)`. */
#include <stdio.h>

const char *pick(int k) {
    const char *n;
    if (k == 0) n = "zero";
    else if (k == 1) n = "one";
    else n = "many";
    return n;
}

const char *yn(int x) { if (x) return "yes"; return "no"; }

int main(void) {
    for (int i = 0; i < 3; i++)
        printf("%s\n", pick(i));
    const char *s = yn(1);
    printf("%s %s\n", s, yn(0));
    printf("%s\n", pick(5));
    return 0;
}
