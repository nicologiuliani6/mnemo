#include <stdio.h>
#include <stdlib.h>
#include <string.h>

struct P{int x;};
int main(void){struct P a[4];for(int i=0;i<4;i++)a[i].x=i;for(int i=0;i<4;i++)a[i].x*=a[i].x;printf("%d %d %d %d\n",a[0].x,a[1].x,a[2].x,a[3].x);return 0;}
