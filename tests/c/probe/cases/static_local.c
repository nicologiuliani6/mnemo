// SKIP: design/UB/unspecified divergence (int 64-bit, ptr=1word=4B, arg-eval-order)
#include <stdio.h>

int counter(void){static int c=0;return ++c;}
int main(void){printf("%d %d %d\n",counter(),counter(),counter());return 0;}
