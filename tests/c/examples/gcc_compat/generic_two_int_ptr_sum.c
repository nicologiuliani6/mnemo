#include "compat_runtime.h"

int main(void) {
    int *a = (int *)malloc(sizeof(int));
    int *b = (int *)malloc(sizeof(int));
    *a = 3;
    *b = 5;
    printf("%d\n", *a + *b);
    free(a);
    free(b);
    return 0;
}
