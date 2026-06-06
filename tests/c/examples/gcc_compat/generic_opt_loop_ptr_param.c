/* opt-uncall su ptr-param-writer in loop (vedi c_test/opt_loop_ptr_param.c). */
#include <stdio.h>
#include <stdlib.h>

void fill(int *out, int v) { int *p = malloc(sizeof(int)); p[0] = v * 2; *out = p[0]; free(p); }

int main(void) {
    int sum = 0;
    for (int i = 0; i < 10; i++) { int r = 0; fill(&r, i); sum += r; }
    printf("%d\n", sum);
    int prod = 1;
    for (int i = 1; i <= 5; i++) { int r = 0; fill(&r, i); prod += r; }
    printf("%d\n", prod);
    return 0;
}
