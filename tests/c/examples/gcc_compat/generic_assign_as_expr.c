/* Assignment-as-expression: il valore di `a = E` è E, e l'assegnamento
   è side effect. Coperti:
   - chained: `a = b = c = 7;`
   - decl init: `int x = (a = 5);`
   - binary operand: `int x = (a = 7) + (b = 8);`
   - if/while condition: `if ((y = 42) > 0)`.
   In `_eval_expr` per c.Assignment: lower come stmt + leggi lvalue. */
#include <stdio.h>

int main(void) {
    int a, b, c;
    a = b = c = 11;
    printf("ABC: %d %d %d\n", a, b, c);

    int x = (a = 7) + (b = 8);
    printf("X: %d  AB: %d %d\n", x, a, b);

    int y;
    if ((y = 42) > 0) printf("Y in if: %d\n", y);

    int z = 0;
    while ((z = z + 1) < 4) printf("z=%d\n", z);
    printf("final z=%d\n", z);

    /* nested ternario con assign */
    int w = (a = 100) > 50 ? (b = 1) : (b = 2);
    printf("W: %d B: %d\n", w, b);
    return 0;
}
