#include <stdio.h>

int main(void){int m[3][3];for(int i=0;i<3;i++)for(int j=0;j<3;j++)m[i][j]=i*3+j;printf("%d %d %d\n",m[0][0],m[1][1],m[2][2]);return 0;}
