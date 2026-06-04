// SKIP: pointer-to-array `int(*r)[N]` (row pointer) non supportato (niche)
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int main(void){int m[3][4];for(int i=0;i<3;i++)for(int j=0;j<4;j++)m[i][j]=i*4+j;int(*r)[4]=m;printf("%d %d\n",r[1][2],(*(r+2))[3]);return 0;}
