#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

struct V{int a,b,c;};
int sum(struct V v){v.a+=10;return v.a+v.b+v.c;}
int main(void){struct V x={1,2,3};int r=sum(x);printf("%d %d %d %d\n",r,x.a,x.b,x.c);return 0;}
