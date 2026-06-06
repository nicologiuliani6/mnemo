/* `char *p = a;` con `a` di tipo `char[N]`: bind di p al payload
   dell'array, così `printf("%s", p)` stampa "a". Estende il binding
   stringa già esistente per `const char *b = a;` quando `a` è un
   char_ptr letterale. */
#include <stdio.h>

int main(void) {
    char a[] = "alpha";
    char b[] = "beta";
    char *p = a;
    char *q = b;
    char *r = p;            /* catena: r → p → a */
    printf("%s %s %s\n", p, q, r);
    a[0] = 'A';             /* mutazione visibile via p */
    printf("%s\n", p);
    return 0;
}
