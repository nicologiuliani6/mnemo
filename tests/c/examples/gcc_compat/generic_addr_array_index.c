/* `&a[K]` ≡ `a + K`: indirizzo di un elemento puntato. */
#include <stdio.h>

int sum_range(int *start, int *end) {
    int s = 0;
    while (start < end) {
        s += *start;
        start++;
    }
    return s;
}

int main(void) {
    int a[5] = {10, 20, 30, 40, 50};
    int *p = &a[2];
    int total = sum_range(&a[0], &a[5]);
    int mid = sum_range(&a[1], &a[4]);
    printf("%d %d %d\n", *p, total, mid);
    return *p + (total / 10);
}
