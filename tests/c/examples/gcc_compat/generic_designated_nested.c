/* Designated init multi-D: partial designator + nested InitList. */
#include <stdio.h>
int main(void) {
    int m[3][3] = {[0]={1,2,3}, {4,5,6}, [2][2]=99};
    int n[2][2][2] = {[1]={{8,9},{10,11}}};
    int s = 0;
    for (int i = 0; i < 3; i++)
        for (int j = 0; j < 3; j++)
            s += m[i][j];
    printf("%d %d %d\n", m[2][2], n[1][1][1], s);
    return s;
}
