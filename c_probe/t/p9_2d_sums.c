#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int main(void){int m[3][4];for(int i=0;i<3;i++)for(int j=0;j<4;j++)m[i][j]=i*4+j;
int rs=0,cs=0;for(int j=0;j<4;j++)cs+=m[1][j];for(int i=0;i<3;i++)rs+=m[i][2];
printf("%d %d\n",rs,cs);return 0;}
