#include <stdio.h>
#include <stdlib.h>

int main(void) {
    div_t a = (div_t){17/5, 17%5};
    printf("q=%d r=%d\n", a.quot, a.rem);
    return 0;
}
