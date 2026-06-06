#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int main(void){int a[4][4];for(int i=0;i<4;i++)for(int j=0;j<4;j++)a[i][j]=i*4+j;
int s=0;for(int k=0;k<4;k++)s+=a[k][3-k];printf("%d\n",s);return 0;}
