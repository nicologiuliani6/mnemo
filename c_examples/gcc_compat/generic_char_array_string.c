/* `char s[] = "literal"` con dim inferita + scan byte-per-byte fino a NUL. */
#include <stdio.h>

int main(void) {
    char s[] = "hello";
    int n = 0;
    for (int i = 0; s[i] != '\0'; i++) n++;
    for (int i = 0; s[i] != '\0'; i++) printf("%c", s[i]);
    printf("\n%d\n", n);
    return n;
}
