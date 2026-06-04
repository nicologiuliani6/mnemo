#include <stdio.h>
#include <stdlib.h>
#include <string.h>

struct P{int x;int y;};
void swap(struct P*a,struct P*b){struct P t=*a;*a=*b;*b=t;}
int main(void){struct P a={1,2},b={3,4};swap(&a,&b);printf("%d %d %d %d\n",a.x,a.y,b.x,b.y);return 0;}
