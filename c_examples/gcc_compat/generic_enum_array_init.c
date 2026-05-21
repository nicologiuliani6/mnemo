/* `enum Color` come elemento di array + init file-scope con valore enum. */
#include <stdio.h>

enum Color { RED = 1, GREEN = 2, BLUE = 4, ALL = RED | GREEN | BLUE };

enum Color c_global = RED;

int main(void) {
    enum Color cs[3] = {RED, GREEN, BLUE};
    int s = 0;
    for (int i = 0; i < 3; i++) s += cs[i];
    printf("%d %d %d\n", c_global, s, ALL);
    return c_global + s + ALL;
}
