/* strlen/strcmp compile-time su stringa letterale o char* con init literal.
   Mnemo restituisce -1/+1 come gcc (segno di strcmp). */
#include <stdio.h>
#include <string.h>

int main(void) {
    int la = strlen("hello");
    int lb = strlen("");
    const char *p = "ciao mondo";
    int lc = strlen(p);
    int eq = strcmp("abc", "abc");
    int lt = strcmp("abc", "abd");
    int gt = strcmp("abd", "abc");
    printf("%d %d %d %d %d %d\n", la, lb, lc, eq, lt, gt);
    return la + lb + lc + eq + lt + gt;
}
