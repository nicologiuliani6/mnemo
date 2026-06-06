#include <stdio.h>
#include <stdlib.h>
#include <string.h>

struct P{int a[3];};
int main(void){struct P p={{1,2,3}};struct P*q=&p;q->a[1]=99;printf("%d %d %d\n",p.a[0],p.a[1],p.a[2]);return 0;}
