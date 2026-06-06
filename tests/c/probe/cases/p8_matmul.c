#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int main(void){int A[2][2]={{1,2},{3,4}},B[2][2]={{5,6},{7,8}},C[2][2]={{0,0},{0,0}};
for(int i=0;i<2;i++)for(int j=0;j<2;j++)for(int k=0;k<2;k++)C[i][j]+=A[i][k]*B[k][j];
printf("%d %d %d %d\n",C[0][0],C[0][1],C[1][0],C[1][1]);return 0;}
