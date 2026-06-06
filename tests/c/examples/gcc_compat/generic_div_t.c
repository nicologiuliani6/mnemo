/* div_t/ldiv_t/lldiv_t via compound literal AST rewrite. */
#include <stdio.h>
#include <stdlib.h>

int main(void) {
    div_t a = div(17, 5);
    div_t b = div(-17, 5);
    ldiv_t c = ldiv(100, 7);
    lldiv_t d = lldiv(1000, 13);

    printf("a.quot=%d a.rem=%d\n", a.quot, a.rem);
    printf("b.quot=%d b.rem=%d\n", b.quot, b.rem);
    printf("c.quot=%ld c.rem=%ld\n", c.quot, c.rem);
    printf("d.quot=%lld d.rem=%lld\n", d.quot, d.rem);

    return 0;
}
