/* File-scope array: alloc + init list, accesso da user fn + main. */
#include <stdio.h>

int g_arr[5] = {2, 4, 6, 8, 10};
int g_scratch[3];

int sum_all(void) {
    int s = 0;
    for (int k = 0; k < 5; k++) s += g_arr[k];
    return s;
}

int main(void) {
    g_scratch[0] = 100;
    g_scratch[1] = 200;
    g_scratch[2] = 300;
    int t = sum_all();
    printf("%d %d %d %d\n", t, g_scratch[0], g_scratch[1], g_scratch[2]);
    return t + g_scratch[0] + g_scratch[1] + g_scratch[2];
}
