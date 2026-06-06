#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int main(void){int R=4,C=5;int*g=malloc(sizeof(int)*R*C);
for(int i=0;i<R;i++)for(int j=0;j<C;j++)g[i*C+j]=i*10+j;
int s=0;for(int i=0;i<R*C;i++)s+=g[i];printf("%d\n",s);free(g);return 0;}
