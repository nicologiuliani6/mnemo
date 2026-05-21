/* `printf("%s", arr)` su `char arr[] = "literal";`. */
#include <stdio.h>

int main(void) {
    char a[] = "Hello";
    char b[] = "world";
    printf("%s, %s!\n", a, b);
    /* Mutate poi reprint */
    a[0] = 'h';
    printf("%s\n", a);
    return 0;
}
