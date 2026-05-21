/* Bit-field con truncamento al numero di bit dichiarato. Mnemo
   trunca solo quando rhs è valutabile a compile-time (`(1<<N)-1`
   const-folded immediatamente). Caso runtime ancora non supportato
   per costo `&` via bits.kairos. Test usa solo valori entro range
   per evitare warning gcc. */
#include <stdio.h>

struct F {
    unsigned a : 3;
    unsigned b : 5;
    unsigned c : 8;
};

int main(void) {
    struct F f = {0};
    f.a = 7;          /* 7 max in 3 bit */
    f.b = 31;         /* 31 max in 5 bit */
    f.c = 255;        /* 255 max in 8 bit */
    printf("%u %u %u\n", f.a, f.b, f.c);

    f.a = 1;          /* riassegnamento */
    f.b = 16;
    f.c = 128;
    printf("%u %u %u\n", f.a, f.b, f.c);

    f.a = 7 & 7;      /* 7 */
    f.b = 31 & 31;    /* 31 */
    printf("%u %u\n", f.a, f.b);
    return 0;
}
