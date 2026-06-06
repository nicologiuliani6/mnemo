#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int main(void){int t[2][2][2];int c=0;for(int i=0;i<2;i++)for(int j=0;j<2;j++)for(int k=0;k<2;k++)t[i][j][k]=c++;
int s=0;for(int i=0;i<2;i++)for(int j=0;j<2;j++)for(int k=0;k<2;k++)s+=t[i][j][k]*(i+j+k+1);printf("%d\n",s);return 0;}
