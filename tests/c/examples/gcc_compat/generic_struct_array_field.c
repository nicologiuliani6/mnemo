/* arr[i].campo su array-di-struct top-level (file-scope) e locale.
   Indice costante e runtime; assegnamento `=` e compound; read. */
#include <stdio.h>

typedef struct { int x; int y; } P;
P g[4];

int main(void) {
    /* runtime index write su array-di-struct file-scope */
    for (int i = 0; i < 4; i++) {
        g[i].x = i;
        g[i].y = i * 10;
    }
    /* compound su indice costante */
    g[2].x += 100;
    /* runtime index read */
    int s = 0;
    for (int j = 0; j < 4; j++) {
        s += g[j].x + g[j].y;
    }
    printf("file: %d %d %d\n", g[0].y, g[2].x, s);

    /* stesso pattern su array-di-struct locale */
    P loc[3];
    for (int k = 0; k < 3; k++) {
        loc[k].x = k + 1;
        loc[k].y = k * k;
    }
    loc[1].y += 5;
    printf("loc: %d %d %d\n", loc[0].x, loc[1].y, loc[2].y);
    return 0;
}
