// transaction.c — aggiornamento transazionale di un array SENZA snapshot,
// usando il backtracking integrato (try/rollback).
//
// Un magazzino `stock[]` evade ordini: ogni ordine sottrae quantità da più
// slot. L'ordine è valido solo se nessuno slot va negativo.
//
// Approccio classico (snapshot/restore):
//   int backup[N]; memcpy(backup, stock, sizeof stock);   // copia O(N)
//   /* applica l'ordine in-place */
//   if (invalido) memcpy(stock, backup, sizeof stock);     // ripristino
// → serve memoria per il backup + codice di salva/ripristina da tenere
//   sincronizzato con lo stato.
//
// Con try/rollback non serve NESSUN backup: si applica l'ordine in-place e,
// se la condizione di validità non regge, la rollback inverte automaticamente
// tutte le scritture (lo `stock` torna esattamente com'era). L'undo è l'inverso
// provabilmente corretto del body — niente copie, niente codice di restore.

#include <stdio.h>

#define N 5

static void print_stock(int s[N]) {
    int i;
    for (i = 0; i < N; i++) printf("%d ", s[i]);
    printf("\n");
}

int main(void) {
    int stock[N] = {5, 3, 8, 2, 6};

    // Ordine 1: chiede 9 dallo slot 2 (disponibili 8) → NON evadibile.
    int order1[N] = {2, 1, 9, 0, 1};
    int viol = 0;
    int i = 0;
    try (viol == 0) {
        for (i = 0; i < N; i++) {
            stock[i] -= order1[i];
            if (stock[i] < 0) viol += 1;
        }
    } rollback {
        // ordine rifiutato: `stock` ripristinato automaticamente (nessun backup)
    }
    printf("dopo ordine 1 (rifiutato): ");
    print_stock(stock);            // invariato: 5 3 8 2 6

    // Ordine 2: tutte le quantità disponibili → evadibile, viene applicato.
    int order2[N] = {2, 1, 3, 0, 1};
    int viol2 = 0;
    try (viol2 == 0) {
        for (i = 0; i < N; i++) {
            stock[i] -= order2[i];
            if (stock[i] < 0) viol2 += 1;
        }
    } rollback {
    }
    printf("dopo ordine 2 (evaso):    ");
    print_stock(stock);            // applicato: 3 2 5 2 5

    return 0;
}
