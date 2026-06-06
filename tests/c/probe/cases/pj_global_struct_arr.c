#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

struct P{int x,y;};
struct P g[3]={{1,2},{3,4},{5,6}};
int main(void){int s=0;for(int i=0;i<3;i++)s+=g[i].x*g[i].y;g[1].x=10;s+=g[1].x;printf("%d\n",s);return 0;}
