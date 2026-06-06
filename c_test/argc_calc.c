#include <stdio.h>

/* Input da riga di comando: usa `argc` come numero N (quante volte e' stato
   lanciato con argomenti). Mnemo: argv e' uno stub sintattico, ma argc e' reale
   e si imposta con `--main-argc N` / `MAIN_ARGC=N`. gcc: lancia con N-1 argomenti.

   Calcola: tabella delle somme parziali e dei fattoriali fino a N, piu' un
   FizzBuzz su [1..3N]. Tutto deterministico in funzione di argc. */

static long fact(int n) {
    long r = 1;
    for (int i = 2; i <= n; i++) r *= i;
    return r;
}

int main(int argc, char **argv) {
    /* evita warning unused; argv non e' dereferenziato (stub in Mnemo) */
    (void)argv;
    int n = argc;
    if (n < 1) n = 1;
    if (n > 12) n = 12;

    int sum = 0;
    for (int i = 1; i <= n; i++) {
        sum += i;
        printf("i=%d sum=%d fact=%ld\n", i, sum, fact(i));
    }

    int fizz = 0, buzz = 0, fb = 0, other = 0;
    for (int k = 1; k <= 3 * n; k++) {
        if (k % 15 == 0) fb++;
        else if (k % 3 == 0) fizz++;
        else if (k % 5 == 0) buzz++;
        else other++;
    }
    printf("argc=%d fizz=%d buzz=%d fizzbuzz=%d other=%d\n",
           argc, fizz, buzz, fb, other);
    return n;
}
