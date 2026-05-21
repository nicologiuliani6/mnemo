/* sizeof su espressione (non solo tipo/nome): a[i], s.field, *p. */
#include <stdio.h>
struct P { int x; int y; };

int main(void) {
    int a[5] = {1, 2, 3, 4, 5};
    int n_elem = sizeof(a) / sizeof(a[0]);
    struct P p = {1, 2};
    int *q = a;
    printf("%d %d %d %d\n",
           n_elem,
           (int)sizeof(a[2]),
           (int)sizeof(p.x),
           (int)sizeof(*q));
    int s = 0;
    for (int i = 0; i < n_elem; i++) s += a[i];
    return s;
}
