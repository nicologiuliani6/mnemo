/* `<stdbool.h>`: alias `bool`/`true`/`false`. */
#include <stdio.h>
#include <stdbool.h>

bool is_even(int n) {
    return (n % 2) == 0;
}

int main(void) {
    bool t = true;
    bool f = false;
    bool e2 = is_even(2);
    bool e7 = is_even(7);
    int s = (int)t + (int)f + (int)e2 + (int)e7;
    printf("%d %d %d %d %d\n", t, f, e2, e7, s);
    return s;
}
