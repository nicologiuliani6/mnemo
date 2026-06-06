#include <stdio.h>

/* Conway's Game of Life su griglia W x H con bordi morti. Stato iniziale
   hard-coded (un glider). Evolve N generazioni, stampa la griglia finale e il
   numero di celle vive. Deterministico, niente input. */

#define W 12
#define H 10
#define GENS 12

static int grid[H][W];
static int next[H][W];

static int neighbors(int y, int x) {
    int n = 0;
    for (int dy = -1; dy <= 1; dy++) {
        for (int dx = -1; dx <= 1; dx++) {
            if (dy == 0 && dx == 0) continue;
            int ny = y + dy, nx = x + dx;
            if (ny < 0 || ny >= H || nx < 0 || nx >= W) continue;
            n += grid[ny][nx];
        }
    }
    return n;
}

int main(void) {
    for (int y = 0; y < H; y++)
        for (int x = 0; x < W; x++)
            grid[y][x] = 0;

    /* glider in alto a sinistra */
    grid[0][1] = 1;
    grid[1][2] = 1;
    grid[2][0] = 1;
    grid[2][1] = 1;
    grid[2][2] = 1;

    for (int g = 0; g < GENS; g++) {
        for (int y = 0; y < H; y++) {
            for (int x = 0; x < W; x++) {
                int n = neighbors(y, x);
                if (grid[y][x])
                    next[y][x] = (n == 2 || n == 3) ? 1 : 0;
                else
                    next[y][x] = (n == 3) ? 1 : 0;
            }
        }
        for (int y = 0; y < H; y++)
            for (int x = 0; x < W; x++)
                grid[y][x] = next[y][x];
    }

    int alive = 0;
    for (int y = 0; y < H; y++) {
        for (int x = 0; x < W; x++) {
            putchar(grid[y][x] ? '#' : '.');
            alive += grid[y][x];
        }
        putchar('\n');
    }
    printf("gen=%d alive=%d\n", GENS, alive);
    return 0;
}
