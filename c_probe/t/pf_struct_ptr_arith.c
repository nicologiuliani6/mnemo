#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

struct P{int x,y;};
int main(void){struct P a[5]={{0,0},{1,1},{2,4},{3,9},{4,16}};struct P*p=a;
int s=0;for(int i=0;i<5;i++){s+=(p+i)->x+(p+i)->y;}p+=4;s+=p->y;printf("%d\n",s);return 0;}
