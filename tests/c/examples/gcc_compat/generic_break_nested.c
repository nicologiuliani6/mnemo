/* break in inner loop nested in outer loop: only inner exits, outer continues.
   Tests that br_v of inner is correctly reset between outer iterations. */
#include <stdio.h>

int main(void) {
    int s = 0;
    for (int i = 0; i < 3; i += 1) {
        for (int j = 0; j < 10; j += 1) {
            if (j == 3) break;
            s += i * 10 + j;
        }
    }
    printf("%d\n", s);
    return s;
}
