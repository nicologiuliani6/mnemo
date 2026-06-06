/* REGRESSION: OR/AND/XOR bit-a-bit preservano il bit 31 (segno).
 * Fix lib/bits.kairos: __mn_and_into/__mn_or_into aggiungono uno step bit-31
 * in complemento a 2 (contributo -2^31). Prima: -5|8 → 2147483643, -1&-1 →
 * 2147483647. NB: il bitwise in interprete puro è O(value) sugli operandi
 * grandi (lento/hang); usare --native-arith per quelli (bypassa bits.kairos).
 * Atteso: -5 -1 -6 4 -5.
 */
#ifdef MNEMO
int printf(const char *fmt, ...);
#else
#include <stdio.h>
#endif
int main(void){
    int x=-5, y=-1;
    printf("%d %d %d %d %d\n", x|8, y&y, x^1, ~x, x&y);
    return 0;
}
