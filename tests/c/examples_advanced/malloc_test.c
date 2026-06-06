#include <stdio.h>
#include <stdlib.h>

void foo(int* p){
    for(int i=0; i<100; i++){
        p = malloc(i);
        //free(p);
    }
}

int main(void){
    int *p; 
    foo(p);
    return 0;
}