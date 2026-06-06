#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int main(void){int m[3][3];int*p=&m[0][0];for(int i=0;i<9;i++)p[i]=i;printf("%d %d %d\n",m[0][0],m[1][1],m[2][2]);return 0;}
