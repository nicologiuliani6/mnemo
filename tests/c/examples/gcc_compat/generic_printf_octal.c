/* printf("%o", costante): formato ottale per letterale int.
   (Argomenti runtime non supportati: lib `puto` non implementata.) */
#include <stdio.h>

int main(void) {
    printf("%o %o %o\n", 8, 64, 511);  /* 10 100 777 */
    printf("%o %x\n", 0xff, 0xff);     /* 377 ff */
    printf("[%o]\n", 0);               /* [0] */
    return 0;
}
