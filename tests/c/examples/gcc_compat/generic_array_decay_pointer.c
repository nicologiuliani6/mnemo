/* Array-to-pointer decay in r-value: `int *p = a;` su `int a[N]`. */
#include <stdio.h>

int main(void) {
    int a[5] = {1, 2, 3, 4, 5};
    int *p = a;
    p++;
    p++;
    int *q = p + 1;
    int diff = q - a;
    printf("%d %d %d\n", *p, *q, diff);
    return *p + *q + diff;
}
