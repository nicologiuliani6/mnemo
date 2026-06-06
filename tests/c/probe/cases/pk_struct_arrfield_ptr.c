#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

struct V{int d[4];};
int main(void){struct V v={{1,2,3,4}};struct V*p=&v;int s=0;for(int i=0;i<4;i++)s+=p->d[i];p->d[0]=100;s+=p->d[0];printf("%d\n",s);return 0;}
