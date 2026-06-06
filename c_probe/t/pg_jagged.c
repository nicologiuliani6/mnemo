#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int main(void){int R=3;int**g=malloc(sizeof(int*)*R);int len[3]={2,3,4};
for(int i=0;i<R;i++){g[i]=malloc(sizeof(int)*len[i]);for(int j=0;j<len[i];j++)g[i][j]=i*10+j;}
int s=0;for(int i=0;i<R;i++)for(int j=0;j<len[i];j++)s+=g[i][j];
for(int i=0;i<R;i++)free(g[i]);free(g);printf("%d\n",s);return 0;}
