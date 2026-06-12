// transaction.c — evasione ordini su un magazzino con try/rollback al posto
// di snapshot/restore.
//
// `stock[]` è il magazzino. Scorriamo una lista di `orders`: ogni ordine
// sottrae quantità da più slot ed è evadibile solo se nessuno slot va
// negativo. Iteriamo gli ordini uno a uno: quelli FATTIBILI vengono accettati
// (commit, lo stock resta aggiornato), quelli NON fattibili vengono annullati
// (rollback) e si passa al successivo.
//
// Approccio classico: prima di ogni ordine copi lo stock (snapshot O(N)),
// applichi in-place e su violazione ripristini dal backup. Con try/rollback
// non serve nessun backup: applichi in-place e, se l'ordine non è evadibile,
// la rollback inverte automaticamente tutte le scritture (lo stock torna
// esattamente com'era) — niente copie, niente codice di restore.

#include <stdio.h>

#define N 4    // slot di magazzino
#define M 3    // numero di ordini

int main(void) {
    int stock[N] = {5, 3, 8, 2};
    int orders[M][N] = {
        {2, 1, 9, 0},   // slot 2 chiede 9 > 8 → NON evadibile → rollback
        {1, 1, 1, 1},   // evadibile → accettato
        {0, 2, 7, 0},   // evadibile sullo stock aggiornato → accettato
    };

    int accepted = 0;
    int j = 0;
    for (j = 0; j < M; j++) {
        int viol = 0;
        int i = 0;
        try (viol == 0) {
            // applica l'ordine j in-place; conta gli slot andati negativi
            for (i = 0; i < N; i++) {
                stock[i] -= orders[j][i];
                if (stock[i] < 0) viol += 1;
            }
            accepted += 1;          // tenuto solo se l'ordine è evadibile
        } rollback {
            printf("Ordine %d rifiutato\n", j);
            // ordine non evadibile: stock e accepted ripristinati
            // automaticamente (nessun backup) → passa al prossimo
        }
    }

    printf("ordini accettati: %d  stock finale:", accepted);
    for (j = 0; j < N; j++) printf(" %d", stock[j]);
    printf("\n");
    return accepted;                // atteso: 2 (stock 4 0 0 1)
}
