// SKIP: design/UB/unspecified divergence (int 64-bit, ptr=1word=4B, arg-eval-order)
#include <stdio.h>

int main(void){int a=2000000000;a+=2000000000;printf("%d\n",a);return 0;}
