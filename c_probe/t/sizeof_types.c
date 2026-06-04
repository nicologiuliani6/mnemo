// SKIP: design/UB/unspecified divergence (int 64-bit, ptr=1word=4B, arg-eval-order)
#include <stdio.h>

int main(void){printf("%zu %zu %zu\n",sizeof(int),sizeof(char),sizeof(int*));return 0;}
