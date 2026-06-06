#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

struct V{int v;};
int main(void){struct V arr[5];for(int i=0;i<5;i++)arr[i].v=i*i;
struct V*p=arr;int s=0;for(int i=0;i<5;i++)s+=(p+i)->v;
p+=2;s+=p->v;p--;s+=p->v;printf("%d\n",s);return 0;}
