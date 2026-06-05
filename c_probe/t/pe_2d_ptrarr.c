// SKIP int**g 2D (malloc di array di puntatori, g[i][j]) : doppia indirezione heap non supportata
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int main(void){int R=3,C=4;int**g=malloc(sizeof(int*)*R);for(int i=0;i<R;i++){g[i]=malloc(sizeof(int)*C);for(int j=0;j<C;j++)g[i][j]=i*C+j;}
int s=0;for(int i=0;i<R;i++)for(int j=0;j<C;j++)s+=g[i][j];for(int i=0;i<R;i++)free(g[i]);free(g);printf("%d\n",s);return 0;}
