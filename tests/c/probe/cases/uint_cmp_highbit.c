#include <stdio.h>

unsigned id(unsigned x){return x;}
int main(void){unsigned a=id(0u)-1u,b=id(1u);printf("%d %d %d\n",a>b,a<b,b<a);return 0;}
