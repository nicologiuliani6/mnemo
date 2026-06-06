/* Comma operator in for-init e for-step. */
#include <stdio.h>

int main(void) {
    int s = 0;
    int i, j;
    for (i = 0, j = 10; i < 5; i += 1, j -= 1) s += i + j;
    printf("%d\n", s);
    return s;
}
