/* Letterali interi: ottali `0755`, esadecimali `0xCAFE`, binari `0b1010`,
   suffissi `u`/`l`/`ll` ignorati. */
#include <stdio.h>

int main(void) {
    int oct = 0755;       /* 493 */
    int hex = 0xCAFE;     /* 51966 */
    int bin = 0b1010;     /* 10 */
    int big = 100000UL;
    int neg = -0x10;      /* -16 */
    int zero = 0;
    int sum = oct + bin + neg + zero;
    printf("%d %d %d %d %d %d\n", oct, hex, bin, big, neg, sum);
    return sum;
}
