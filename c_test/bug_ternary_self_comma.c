/* BUG (niche): `x = x ? 1 : (x=2, x+1);` esce 1 SILENZIOSO (no stdout, no
 * messaggio d'errore). Si verifica solo quando lo stesso `x` è (a) lvalue del
 * ternario, (b) letto nella condizione, (c) riassegnato nel ramo via comma.
 * Varianti con cond costante / lvalue diverso / senza comma funzionano.
 * Probabile collisione di cella nel lowering (x dst + read + write). Doppio
 * difetto: risultato errato + fallimento silenzioso (dovrebbe almeno errorare).
 * Atteso 3.
 */
#ifdef MNEMO
int printf(const char *fmt, ...);
#else
#include <stdio.h>
#endif
int main(void){
    int x = 0;
    x = x ? 1 : (x = 2, x + 1);
    printf("%d\n", x);
    return 0;
}
