#include <stdio.h>
#include <stdlib.h>
#include <string.h>

struct P{int x;int y;};
int main(void){struct P*a=malloc(sizeof(struct P)*3);for(int i=0;i<3;i++){a[i].x=i;a[i].y=i*2;}int s=0;for(int i=0;i<3;i++)s+=a[i].x+a[i].y;printf("%d\n",s);free(a);return 0;}
