/* `<limits.h>`: SHRT_MAX, INT_MAX, CHAR_BIT, ecc. (esclusi i casi
   con overflow su INT_MIN che richiedono full 32-bit signed). */
#include <stdio.h>
#include <limits.h>

int main(void) {
    int s = SHRT_MAX / 100;     /* 327 */
    int b = CHAR_BIT;           /* 8 */
    int u = UCHAR_MAX / 5;      /* 51 */
    int sum = s + b + u;
    printf("%d %d %d %d\n", s, b, u, sum);
    return sum;
}
