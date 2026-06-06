#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

struct V{int x,y,z;};
int dot(struct V a,struct V b){return a.x*b.x+a.y*b.y+a.z*b.z;}
struct V add(struct V a,struct V b){struct V r={a.x+b.x,a.y+b.y,a.z+b.z};return r;}
int main(void){struct V a={1,2,3},b={4,5,6};struct V c=add(a,b);printf("%d %d\n",dot(a,b),dot(c,c));return 0;}
