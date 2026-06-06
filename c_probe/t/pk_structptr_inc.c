#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

struct P{int x,y;};
int main(void){struct P a[3]={{1,2},{3,4},{5,6}};struct P*p=a;int s=0;
for(int i=0;i<3;i++){s+=p->x+p->y;p++;}printf("%d\n",s);return 0;}
