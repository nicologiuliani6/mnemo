#include <stdio.h>
#ifdef MNEMO
void *malloc(unsigned n);   /* -DMNEMO non include <stdlib.h> */
#else
#include <stdlib.h>
#endif

int main(void){
    int *p;
    for(int i=0; i<100; i++){
        p = malloc(i);
    }
    return 0;
}