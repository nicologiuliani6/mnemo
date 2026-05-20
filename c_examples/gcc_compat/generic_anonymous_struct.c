/* struct {...} senza tag: Mnemo genera tag sintetico e hoista a file-scope. */
#include <stdio.h>

int main(void) {
    struct { int x; int y; int z; } pos = {3, 5, 7};
    union { int i; int j; } u;
    u.i = 42;
    int sum = pos.x + pos.y + pos.z + u.i;
    printf("%d %d %d %d\n", pos.x, pos.y, pos.z, u.i);
    return sum;
}
