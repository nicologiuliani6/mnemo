#include <stdio.h>

int main(void){int a[2][2][2];int c=0;for(int i=0;i<2;i++)for(int j=0;j<2;j++)for(int k=0;k<2;k++)a[i][j][k]=c++;printf("%d %d\n",a[0][0][0],a[1][1][1]);return 0;}
