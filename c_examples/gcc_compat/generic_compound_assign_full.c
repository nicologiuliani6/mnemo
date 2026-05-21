/* Operatori compound: `+=`, `-=`, `*=`, `/=`, `%=`, `<<=`, `>>=`,
   `&=`, `|=`, `^=`. Regressione: `%=`, `*=`, `/=`, `^=` non
   includevano lib auto. */
#include <stdio.h>

int main(void) {
    int a = 10;
    a += 5;   /* 15 */
    a -= 2;   /* 13 */
    a *= 3;   /* 39 */
    a /= 4;   /* 9 */
    a %= 7;   /* 2 */

    int b = 3;
    b <<= 2;  /* 12 */
    b >>= 1;  /* 6 */
    b &= 14;  /* 6 */
    b |= 1;   /* 7 */
    b ^= 5;   /* 2 */

    printf("%d %d\n", a, b);
    return a + b;
}
