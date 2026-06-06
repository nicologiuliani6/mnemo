/* Designated init multi-D + ArrayRef multi-D require mul.kairos. */
#include <stdio.h>

int main(void) {
    int m[3][3] = {[0][0]=1, [1][1]=5, [2][2]=9};
    int s = 0;
    int i = 0;
    while (i < 3) {
        int j = 0;
        while (j < 3) { s += m[i][j]; j += 1; }
        i += 1;
    }
    printf("%d\n", s);
    return s;
}
