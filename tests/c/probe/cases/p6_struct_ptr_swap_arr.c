#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

struct P{int x,y;};
int main(void){struct P a[3]={{1,2},{3,4},{5,6}};struct P*p=a,*q=a+2;struct P t=*p;*p=*q;*q=t;printf("%d %d %d %d\n",a[0].x,a[0].y,a[2].x,a[2].y);return 0;}
