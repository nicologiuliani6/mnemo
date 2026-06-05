#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

struct P{int x,y;};
int main(void){struct P a[4]={{1,1},{2,4},{3,9},{4,16}};struct P b[4];
for(int i=0;i<4;i++)b[i]=a[3-i];int s=0;for(int i=0;i<4;i++)s+=b[i].x*10+b[i].y;printf("%d\n",s);return 0;}
