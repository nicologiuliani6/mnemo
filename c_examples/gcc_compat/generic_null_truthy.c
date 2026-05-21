/* `if (p)` e `p != NULL` su puntatori: la riserva di slot 0 come
   sentinel NULL evita la collisione con `&v` della prima variabile
   locale. */
#include <stdio.h>
#include <stddef.h>

int main(void) {
    int v = 100;          /* prima variabile locale */
    int *p = &v;
    int *q = NULL;

    int c1 = (p != NULL);  /* 1 */
    int c2 = (q != NULL);  /* 0 */
    int c3 = (p ? 10 : 20); /* 10 */
    int c4 = (q ? 10 : 20); /* 20 */

    if (p) printf("p truthy\n");
    if (!q) printf("q falsy\n");

    printf("%d %d %d %d\n", c1, c2, c3, c4);
    return c1 + c3 + c4;
}
