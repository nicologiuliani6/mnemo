#include <stdio.h>

int main(void){int x=7;int*p=&x;int**pp=&p;**pp=42;printf("%d\n",x);return 0;}
