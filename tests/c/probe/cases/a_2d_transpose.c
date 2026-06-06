#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int main(void){int m[2][2]={{1,2},{3,4}};for(int i=0;i<2;i++)for(int j=i+1;j<2;j++){int t=m[i][j];m[i][j]=m[j][i];m[j][i]=t;}printf("%d %d %d %d\n",m[0][0],m[0][1],m[1][0],m[1][1]);return 0;}
