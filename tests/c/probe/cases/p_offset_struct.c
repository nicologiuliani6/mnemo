#include <stdio.h>
#include <stdlib.h>
#include <string.h>

struct P{int a;int b;int c;};
int main(void){struct P p={1,2,3};int*ip=&p.b;*ip=99;printf("%d %d %d\n",p.a,p.b,p.c);return 0;}
