/* `%+d` e `% d` su argomento runtime: `__mn_putd_plus` / `__mn_putd_space`
   emettono prepend conditional via guard reversibile sul segno. Niente
   width runtime ancora. */
#include <stdio.h>

int main(void) {
    int a = 5;
    int b = -42;
    int c = 0;

    /* Const */
    printf("[%+d]\n", 7);
    printf("[%+d]\n", -7);
    printf("[% d]\n", 7);
    printf("[% d]\n", -7);

    /* Runtime */
    printf("[%+d]\n", a);     /* +5 */
    printf("[%+d]\n", b);     /* -42 */
    printf("[%+d]\n", c);     /* +0 */
    printf("[% d]\n", a);     /*  5 */
    printf("[% d]\n", b);     /* -42 */
    printf("[% d]\n", c);     /*  0 */
    return 0;
}
