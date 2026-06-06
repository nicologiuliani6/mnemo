/* _Generic con selezione basata sul TIPO dell'espressione di controllo
   (char vs int vs unsigned vs puntatori), risolto in c_lower con i tipi noti. */
#include <stdio.h>

int main(void) {
    char c = 'A';
    int i = 5;
    unsigned u = 9u;
    int *p = 0;
    char *s = "x";

    /* char e int distinti anche con entrambe le clausole presenti */
    printf("%d %d\n",
           _Generic((c), char: 1, int: 2, default: 0),
           _Generic((i), char: 1, int: 2, default: 0));
    printf("%d\n", _Generic((u), int: 1, unsigned: 2, default: 0));

    /* puntatori */
    printf("%d %d\n",
           _Generic((p), int*: 1, char*: 2, default: 0),
           _Generic((s), int*: 1, char*: 2, default: 0));

    /* costante carattere ha tipo int in C */
    printf("%d\n", _Generic(('a'), char: 1, int: 2, default: 0));

    /* nessun match -> default */
    printf("%d\n", _Generic((i), unsigned: 1, default: 9));
    return 0;
}
