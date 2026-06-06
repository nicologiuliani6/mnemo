#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

struct C{int v;};
int main(void){struct C arr[4]={{10},{20},{30},{40}};struct C*p=&arr[2];p->v=99;(p-1)->v=88;
int s=0;for(int i=0;i<4;i++)s+=arr[i].v;printf("%d\n",s);return 0;}
