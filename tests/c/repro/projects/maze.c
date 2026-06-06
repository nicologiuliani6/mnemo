#include <stdio.h>

/* BFS: cammino minimo in un labirinto hard-coded. '#' muro, '.' libero.
   Start in alto-sx, goal in basso-dx. Stampa la distanza e la griglia con il
   percorso marcato. Coda circolare su array, niente input. */

#define H 7
#define W 9

int main(void) {
    const char *maze[H] = {
        ".........",
        ".###.###.",
        ".#...#...",
        ".#.###.#.",
        "...#...#.",
        ".#.#.#.#.",
        ".#...#...",
    };
    int dist[H][W];
    int prev[H][W];   /* direzione da cui si e' arrivati: 0=su 1=giu 2=sx 3=dx, -1=start */
    for (int y = 0; y < H; y++)
        for (int x = 0; x < W; x++) { dist[y][x] = -1; prev[y][x] = -2; }

    int qy[H * W], qx[H * W];
    int head = 0, tail = 0;

    qy[tail] = 0; qx[tail] = 0; tail++;
    dist[0][0] = 0; prev[0][0] = -1;

    int dy[4] = {-1, 1, 0, 0};
    int dx[4] = {0, 0, -1, 1};

    while (head < tail) {
        int cy = qy[head], cx = qx[head];
        head++;
        for (int d = 0; d < 4; d++) {
            int ny = cy + dy[d], nx = cx + dx[d];
            if (ny < 0 || ny >= H || nx < 0 || nx >= W) continue;
            if (maze[ny][nx] == '#') continue;
            if (dist[ny][nx] != -1) continue;
            dist[ny][nx] = dist[cy][cx] + 1;
            prev[ny][nx] = d;
            qy[tail] = ny; qx[tail] = nx; tail++;
        }
    }

    int gd = dist[H - 1][W - 1];
    printf("dist=%d visited=%d\n", gd, tail);

    /* ricostruisci il percorso a ritroso e marcalo */
    char out[H][W];
    for (int y = 0; y < H; y++)
        for (int x = 0; x < W; x++)
            out[y][x] = maze[y][x];

    if (gd >= 0) {
        int y = H - 1, x = W - 1;
        while (!(y == 0 && x == 0)) {
            out[y][x] = '*';
            int d = prev[y][x];
            if (d == 0) y += 1;       /* arrivato da sopra → torna giu' */
            else if (d == 1) y -= 1;
            else if (d == 2) x += 1;
            else x -= 1;
        }
        out[0][0] = '*';
    }

    for (int y = 0; y < H; y++) {
        for (int x = 0; x < W; x++)
            putchar(out[y][x]);
        putchar('\n');
    }
    return 0;
}
