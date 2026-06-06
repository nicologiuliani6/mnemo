#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

struct P{int a,b,c;};
int main(void){int n=4;struct P*p=malloc(sizeof(struct P)*n);
for(int i=0;i<n;i++){p[i].a=i;p[i].b=i*2;p[i].c=i*3;}
int s=0;for(int i=0;i<n;i++)s+=p[i].a+p[i].b+p[i].c;printf("%d\n",s);free(p);return 0;}
