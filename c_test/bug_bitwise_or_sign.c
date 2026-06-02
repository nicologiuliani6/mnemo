/* BUG APERTO: OR/AND/XOR bit-a-bit perdono il bit 31 (segno).
 * lib/bits.kairos __mn_and_into/__mn_or_into iterano k=0..30 (`until k==31`),
 * 31 bit: il bit 31 non viene mai impostato né c'è sign-extension.
 *   -5|8  → 2147483643 (0x7FFFFFFB) invece di -5 (0xFFFFFFFB).
 *   -1&-1 → 2147483647 invece di -1.
 * AND/XOR passano nei casi in cui l'operando con bit31 dà 0 nel risultato
 * (es. -5^1, -5&8) → latente. Fix NON banale: dipende dalla signedness
 * (signed int → sign-extend bit31 a -2^31; unsigned → +2^31 con mask u32).
 * RISCHIO ALTO: bits.kairos è usato pesantemente da encrypt/des (round-trip
 * +invertibility) → ogni modifica va riverificata su entrambi.
 * Atteso: -5|8=-5, -1&-1=-1, -5^1=-6, ~-5=4.
 */
#ifdef MNEMO
int printf(const char *fmt, ...);
#else
#include <stdio.h>
#endif
int main(void){
    int x=-5, y=-1;
    printf("%d %d %d %d\n", x|8, y&y, x^1, ~x);
    return 0;
}
