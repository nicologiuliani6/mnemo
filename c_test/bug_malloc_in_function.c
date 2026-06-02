/* BUG APERTO: malloc dentro una funzione NON-main + scrittura attraverso un
 * puntatore-parametro (o malloc in più funzioni) → risultato errato.
 * Causa: `__mn_pool_ctr` è un LOCAL per-funzione che parte da 0 (solo `main`
 * lo inizializza a heap_base, vedi lower_file_to_program). In una funzione il
 * counter=0 → le malloc cadono negli slot < heap_base, che il dispatch ibrido
 * (ptr_pool_kairos) tratta come celle NOMINATE `__mn_mem*` → corruzione +
 * `*out = v` instradato sulla cella sbagliata.
 *   setv(&r): r resta 0 invece di 99.
 * Inizializzare il counter a heap_base in ogni funzione NON basta: due funzioni
 * che allocano (es. main + helper) collidono sugli stessi slot. Fix proprio =
 * `__mn_pool_ctr` come stato GLOBALE condiviso/threaded attraverso le call
 * (come gli stack __mn_hist/__mn_scratch, by-ref nella finestra mem_args) così
 * le allocazioni sono sequenziali tra funzioni. Cambiamento di layout.
 * Atteso 99.
 */
#ifdef MNEMO
int printf(const char *fmt, ...);
void *malloc(unsigned n);
#else
#include <stdio.h>
#include <stdlib.h>
#endif
void setv(int *out){
    int *p = malloc(4);
    p[0] = 99;
    *out = p[0];
}
int main(void){
    int r = 0;
    setv(&r);
    printf("%d\n", r);
    return 0;
}
