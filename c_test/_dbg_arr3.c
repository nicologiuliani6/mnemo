#include <stdio.h>

void fill(int a[4]) {
    int i;
    for (i = 0; i < 4; i++) a[i] = (i + 1) * 10;
}

void use(void) {
    int a[4] = {0};
    fill(a);
    int i;
    for (i = 0; i < 4; i++) printf("%d\n", a[i]);
}

int main(void) {
    use();
    return 0;
}
