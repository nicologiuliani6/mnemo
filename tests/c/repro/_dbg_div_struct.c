#include <stdio.h>

typedef struct { int quot; int rem; } my_div_t;

int main(void) {
    my_div_t r = (my_div_t){17 / 5, 17 % 5};
    printf("q=%d r=%d\n", r.quot, r.rem);
    return 0;
}
