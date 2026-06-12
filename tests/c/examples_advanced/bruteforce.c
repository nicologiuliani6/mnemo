// bruteforce.c — ricerca di PREIMAGE con il backtracking integrato del
// linguaggio (try / rollback).
//
// Cerchiamo la più piccola chiave `key` (0,1,2,…) il cui digest multi-passo
// è uguale a TARGET. Il digest viene calcolato nella cella `digest`.
//
// Perché qui il try/rollback è VERAMENTE comodo:
//   ogni tentativo MUTA `digest` in più passi. Se non combacia, lo stato va
//   riportato com'era per provare la chiave successiva. Con try/rollback si
//   scrive solo il calcolo IN AVANTI: la clausola di rollback annulla
//   AUTOMATICAMENTE e in modo provabilmente corretto tutti i passi del body
//   (è l'inverso esatto della computazione, garantito dalla reversibilità).
//
//   A mano dovresti invece scrivere e mantenere l'undo passo-passo, in ordine
//   inverso e senza errori:
//       digest -= key;  digest ^= (key + 1);  digest -= key;
//   fragile e ripetitivo, e tanto peggio quanto più lungo è il body.

#include <stdio.h>

int main(void) {
    int TARGET = 10;
    int key = 0;
    int digest = 0;

    while (digest != TARGET) {
        try (digest == TARGET) {
            // calcolo in avanti del digest(key) — più passi
            digest += key;
            digest ^= (key + 1);
            digest += key;
        } rollback {
            // miss: `digest` è già stato riportato a 0 dall'inversione
            // automatica del body; prova la chiave successiva
            key += 1;
        }
    }

    printf("key: %d\n", key);   // più piccola chiave con digest == TARGET (3)
    return key;
}
