/* `typedef int vecN[N]; vecN v;` — typedef-of-array. */
#include <stdio.h>

typedef int vec3[3];
typedef int matrow[4];

int main(void) {
    vec3 a = {1, 2, 3};
    vec3 b = {10, 20, 30};
    matrow row = {100, 200, 300, 400};
    int s = 0;
    for (int i = 0; i < 3; i++) s += a[i] + b[i];
    for (int i = 0; i < 4; i++) s += row[i];
    printf("%d %d %d\n", a[2], row[3], s);
    return s;
}
