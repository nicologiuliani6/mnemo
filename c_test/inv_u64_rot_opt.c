// Regression guard: opt-uncall + --native-arith su fn u64 con shift (rotate).
// Bug VM risolto: `mn_floor_div2_signed_hist_undo` decideva il ramo >=0/<0 dal
// `ts` POPPATO invece che dal valore LIVE; su operandi int64 NEGATIVI (high bit
// set, prodotti da `x>>(64-n)`) il segno divergeva dal replay → push/pop count
// mismatch sul native and/or hist → `[VM] POP: stack vuoto! (frame=__mn_shr_into)`.
// Fix: undo live-value-driven (mn_native_arith.h). Eseguire con:
//   mnemo run c_test/inv_u64_rot_opt.c --native-arith --opt-uncall-user-calls
// atteso (== gcc): FEDCBA9876543120  (n=3 da solo: 91A2B3C4D5E6F780)
#include <stdio.h>
#include <stdint.h>
static uint64_t rot(uint64_t x, int k) { return (x << k) | (x >> (64 - k)); }
int main(void) {
    uint64_t a = 0x123456789ABCDEF0ULL;
    uint64_t s = 0;
    for (int i = 1; i < 4; i++) s += rot(a, i);
    printf("%llX\n", (unsigned long long)s);
    return 0;
}
