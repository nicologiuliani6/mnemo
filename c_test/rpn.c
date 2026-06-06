#include <stdio.h>

/* Valutatore RPN (notazione polacca inversa). L'espressione e' una stringa di
   token separati da spazi: cifre = push, +,-,*,/ = operatori binari. Niente
   input interattivo: piu' espressioni hard-coded. Stack su array. */

#define STKMAX 64

static int eval_rpn(const char *s, int *ok) {
    int stack[STKMAX];
    int sp = 0;
    *ok = 1;
    for (int i = 0; s[i]; i++) {
        char c = s[i];
        if (c == ' ') continue;
        if (c >= '0' && c <= '9') {
            if (sp >= STKMAX) { *ok = 0; return 0; }
            stack[sp++] = c - '0';
        } else if (c == '+' || c == '-' || c == '*' || c == '/') {
            if (sp < 2) { *ok = 0; return 0; }
            int b = stack[--sp];
            int a = stack[--sp];
            int r = 0;
            switch (c) {
                case '+': r = a + b; break;
                case '-': r = a - b; break;
                case '*': r = a * b; break;
                case '/': if (b == 0) { *ok = 0; return 0; } r = a / b; break;
            }
            stack[sp++] = r;
        } else {
            *ok = 0;
            return 0;
        }
    }
    if (sp != 1) { *ok = 0; return 0; }
    return stack[0];
}

int main(void) {
    const char *exprs[5] = {
        "3 4 +",          /* 7 */
        "5 1 2 + 4 * + 3 -", /* 5 + (1+2)*4 - 3 = 14 */
        "9 3 /",          /* 3 */
        "2 3 4 * *",      /* 24 */
        "8 2 - 2 /"       /* 3 */
    };
    int total = 0;
    for (int i = 0; i < 5; i++) {
        int ok;
        int v = eval_rpn(exprs[i], &ok);
        printf("expr%d -> %d (ok=%d)\n", i, v, ok);
        if (ok) total += v;
    }
    printf("total=%d\n", total);
    return 0;
}
