/* `const char *b = a;` con `a` char_ptr noto: eredita il binding
   stringa così `printf("%s", b)` continua a funzionare. */
#include <stdio.h>

int main(void) {
    const char *a = "hello";
    const char *b = a;
    const char *c = b;
    char *d = "world";
    char *e = d;
    printf("%s %s %s | %s %s\n", a, b, c, d, e);
    return 0;
}
