#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int main(void){int A=2,B=2,C=2;int***g=malloc(sizeof(int**)*A);
for(int i=0;i<A;i++){g[i]=malloc(sizeof(int*)*B);for(int j=0;j<B;j++){g[i][j]=malloc(sizeof(int)*C);
for(int k=0;k<C;k++)g[i][j][k]=i*4+j*2+k;}}
int s=0;for(int i=0;i<A;i++)for(int j=0;j<B;j++)for(int k=0;k<C;k++)s+=g[i][j][k];
printf("%d\n",s);return 0;}
