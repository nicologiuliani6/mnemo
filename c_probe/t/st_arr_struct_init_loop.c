#include <stdio.h>
#include <stdlib.h>
#include <string.h>

struct P{int x;int y;};
int main(void){struct P a[4];for(int i=0;i<4;i++){a[i].x=i;a[i].y=i*i;}int s=0;for(int i=0;i<4;i++)s+=a[i].x*a[i].y;printf("%d\n",s);return 0;}
