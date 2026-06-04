#include <stdio.h>

struct P{int x;int y;};
int main(void){struct P a[3]={{1,2},{3,4},{5,6}};int s=0;for(int i=0;i<3;i++)s+=a[i].x+a[i].y;printf("%d\n",s);return 0;}
