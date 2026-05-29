/* strcat/strncat runtime byte append. */
#include <stdio.h>
#include <string.h>

int main(void) {
    char a[32] = "hello";
    strcat(a, " world");
    printf("a=%s\n", a);

    char b[16] = "";
    strcat(b, "abc");
    strcat(b, "def");
    printf("b=%s\n", b);

    char c[20] = "xy";
    strncat(c, "0123", 4);
    printf("c=%s\n", c);

    return 0;
}
