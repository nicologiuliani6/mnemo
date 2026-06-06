#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int main(void){int a[2][2]={{1,2},{3,4}};int b[2][2]={{5,6},{7,8}};int c[2][2]={{0,0},{0,0}};for(int i=0;i<2;i++)for(int j=0;j<2;j++)for(int k=0;k<2;k++)c[i][j]+=a[i][k]*b[k][j];printf("%d %d %d %d\n",c[0][0],c[0][1],c[1][0],c[1][1]);return 0;}
