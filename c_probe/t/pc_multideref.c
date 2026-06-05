#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int main(void){int x=42;int*p=&x;int**pp=&p;int***ppp=&pp;***ppp=100;printf("%d %d %d\n",x,*p,**pp);return 0;}
