/* Designated initializer 1D: `int a[N] = {[idx]=val, ...}` */
#include <stdio.h>

int main(void) {
    int a[5] = {[2]=42, [4]=99};
    int b[6] = {1, 2, [4]=50, 60};
    int s = a[0]+a[1]+a[2]+a[3]+a[4];
    int t = b[0]+b[1]+b[2]+b[3]+b[4]+b[5];
    printf("%d %d\n", s, t);
    return s + t;
}
