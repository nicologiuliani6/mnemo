#include <stdio.h>
#include <stdlib.h>
#include <string.h>

struct Box{int*p;};
int main(void){int x=42;struct Box b;b.p=&x;*b.p=100;printf("%d\n",x);return 0;}
