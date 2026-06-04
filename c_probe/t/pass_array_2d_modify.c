#include <stdio.h>
#include <stdlib.h>
#include <string.h>

void inc2d(int m[2][2]){for(int i=0;i<2;i++)for(int j=0;j<2;j++)m[i][j]++;}
int main(void){int m[2][2]={{1,2},{3,4}};inc2d(m);printf("%d %d %d %d\n",m[0][0],m[0][1],m[1][0],m[1][1]);return 0;}
