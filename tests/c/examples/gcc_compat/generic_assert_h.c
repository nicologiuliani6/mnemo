/* `<assert.h>` no-op (modello reversibile non termina). */
#include <stdio.h>
#include <assert.h>

int compute(int x) {
    assert(x > 0);
    assert(x < 1000);
    return x * 2;
}

int main(void) {
    int r = compute(21);
    printf("%d\n", r);
    return r;
}
