/* printf width/flags su argomenti COSTANTI: padding implementato
   tramite formattazione Python-side (caratteri emessi pre-padded).
   Argomenti runtime: width ignorato (limite documentato). */
#include <stdio.h>

int main(void) {
    printf("[%5d]\n", 42);        /* [   42] */
    printf("[%-5d]\n", 42);       /* [42   ] */
    printf("[%05d]\n", 42);       /* [00042] */
    printf("[%5d]\n", -7);        /* [   -7] */
    printf("[%05d]\n", -7);       /* [-0007] */
    printf("[%4x]\n", 0xAB);      /* [  ab] */
    printf("[%04x]\n", 0xAB);     /* [00ab] */
    return 0;
}
