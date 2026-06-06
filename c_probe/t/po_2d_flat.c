#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int main(void){int R=3,C=4;int*g=malloc(sizeof(int)*R*C);
for(int i=0;i<R;i++)for(int j=0;j<C;j++)g[i*C+j]=i*C+j;
int s=0;for(int i=0;i<R*C;i++)s+=g[i];free(g);printf("%d\n",s);return 0;}
