#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

struct In{int a,b;};struct Out{struct In i;int tag;};
void cp(struct Out*d,struct Out*s){*d=*s;}
int main(void){struct Out x={{3,4},7};struct Out y;cp(&y,&x);y.i.a=99;
printf("%d %d %d | %d %d %d\n",x.i.a,x.i.b,x.tag,y.i.a,y.i.b,y.tag);return 0;}
