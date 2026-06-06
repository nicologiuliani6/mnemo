#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

struct V{int d[3];};
struct V add(struct V a,struct V b){struct V r;for(int i=0;i<3;i++)r.d[i]=a.d[i]+b.d[i];return r;}
int main(void){struct V x={{1,2,3}},y={{10,20,30}};struct V z=add(x,y);printf("%d %d %d\n",z.d[0],z.d[1],z.d[2]);return 0;}
