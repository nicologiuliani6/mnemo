#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int main(void){int x=5;int*p=&x;int**q=&p;int***r=&q;***r=42;printf("%d\n",x);return 0;}
