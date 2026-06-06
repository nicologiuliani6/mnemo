#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int diag(int m[4][4]){int s=0;for(int i=0;i<4;i++)s+=m[i][i];return s;}
int main(void){int m[4][4];for(int i=0;i<4;i++)for(int j=0;j<4;j++)m[i][j]=i*4+j;printf("%d\n",diag(m));return 0;}
