#include <stdio.h>

int sum2d(int m[2][3]){int s=0;for(int i=0;i<2;i++)for(int j=0;j<3;j++)s+=m[i][j];return s;}
int main(void){int m[2][3]={{1,2,3},{4,5,6}};printf("%d\n",sum2d(m));return 0;}
