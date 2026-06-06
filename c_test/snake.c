#include <stdio.h>
#include <stdlib.h>

/* Snake su griglia W x H. Niente input interattivo: le mosse arrivano da una
   stringa di comandi (w/a/s/d). Cibo posizionato in modo deterministico con un
   LCG, così l'output e' riproducibile e confrontabile con gcc 1:1. */

#define W 10
#define H 8
#define MAXLEN (W * H)

/* LCG deterministico (Numerical Recipes) per piazzare il cibo. */
static unsigned rng_state = 12345u;
static unsigned next_rand(void) {
    rng_state = rng_state * 1664525u + 1013904223u;
    return rng_state;
}

int main(void) {
    /* Corpo del serpente: code circolare di coordinate. body[0]=coda ...
       body[len-1]=testa. Memorizzo x e y in array paralleli. */
    int sx[MAXLEN], sy[MAXLEN];
    int len = 3;
    /* serpente iniziale orizzontale al centro */
    sx[0] = 3; sy[0] = 4;
    sx[1] = 4; sy[1] = 4;
    sx[2] = 5; sy[2] = 4;

    int dx = 1, dy = 0; /* direzione iniziale: destra */

    /* griglia di occupazione: 1 = corpo serpente */
    int occ[H][W];
    for (int y = 0; y < H; y++)
        for (int x = 0; x < W; x++)
            occ[y][x] = 0;
    for (int i = 0; i < len; i++)
        occ[sy[i]][sx[i]] = 1;

    /* primo cibo */
    int fx = next_rand() % W;
    int fy = next_rand() % H;
    while (occ[fy][fx]) {
        fx = next_rand() % W;
        fy = next_rand() % H;
    }

    /* sequenza di comandi (cibo previsto lungo il percorso) */
    const char *cmds = "dddwwsssaaddwwd";
    int score = 0;
    int alive = 1;
    int steps = 0;

    for (int c = 0; cmds[c] != '\0' && alive; c++) {
        char m = cmds[c];
        /* aggiorna direzione, vietando l'inversione a 180 gradi */
        if (m == 'w' && dy != 1) { dx = 0; dy = -1; }
        else if (m == 's' && dy != -1) { dx = 0; dy = 1; }
        else if (m == 'a' && dx != 1) { dx = -1; dy = 0; }
        else if (m == 'd' && dx != -1) { dx = 1; dy = 0; }

        int hx = sx[len - 1] + dx;
        int hy = sy[len - 1] + dy;

        /* collisione con i muri */
        if (hx < 0 || hx >= W || hy < 0 || hy >= H) {
            alive = 0;
            break;
        }
        /* collisione con se stesso (la coda si liberera' se non mangia) */
        int ate = (hx == fx && hy == fy);
        if (occ[hy][hx] && !(ate == 0 && hx == sx[0] && hy == sy[0])) {
            alive = 0;
            break;
        }

        if (ate) {
            /* cresci: sposta testa, mantieni la coda */
            for (int i = len; i > 0; i--) {
                sx[i] = sx[i - 1];
                sy[i] = sy[i - 1];
            }
            sx[len] = hx; sy[len] = hy;
            /* l'ordinamento sopra e' sbagliato per una coda: rifaccio in modo
               semplice spostando tutti gli elementi in avanti */
            len++;
            occ[hy][hx] = 1;
            score += 10;
            /* nuovo cibo */
            fx = next_rand() % W;
            fy = next_rand() % H;
            while (occ[fy][fx]) {
                fx = next_rand() % W;
                fy = next_rand() % H;
            }
        } else {
            /* muovi: libera la coda, scorri il corpo, aggiungi testa */
            occ[sy[0]][sx[0]] = 0;
            for (int i = 0; i < len - 1; i++) {
                sx[i] = sx[i + 1];
                sy[i] = sy[i + 1];
            }
            sx[len - 1] = hx; sy[len - 1] = hy;
            occ[hy][hx] = 1;
        }
        steps++;
    }

    /* stampa la griglia finale: '#' bordo implicito via coordinate, 'O' testa,
       'o' corpo, '*' cibo, '.' vuoto */
    for (int i = 0; i < len; i++)
        occ[sy[i]][sx[i]] = 1;
    for (int y = 0; y < H; y++) {
        for (int x = 0; x < W; x++) {
            char ch = '.';
            if (x == sx[len - 1] && y == sy[len - 1]) ch = 'O';
            else if (occ[y][x]) ch = 'o';
            else if (x == fx && y == fy) ch = '*';
            putchar(ch);
        }
        putchar('\n');
    }

    printf("alive=%d len=%d score=%d steps=%d\n", alive, len, score, steps);
    return 0;
}
