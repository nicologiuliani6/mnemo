#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int main(void){int m[3][4];for(int i=0;i<3;i++)for(int j=0;j<4;j++)m[i][j]=i*4+j;
int(*r)[4]=m;int s=0;for(int i=0;i<3;i++)for(int j=0;j<4;j++)s+=r[i][j];printf("%d\n",s);return 0;}
