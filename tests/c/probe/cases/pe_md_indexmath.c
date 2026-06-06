#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int main(void){int m[5][5];for(int i=0;i<5;i++)for(int j=0;j<5;j++)m[i][j]=(i-j)*(i-j);
int s=0;for(int i=0;i<5;i++)for(int j=0;j<5;j++)if((i+j)%2==0)s+=m[i][j];printf("%d\n",s);return 0;}
