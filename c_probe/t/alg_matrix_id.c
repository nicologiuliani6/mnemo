#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int main(void){int m[4][4];for(int i=0;i<4;i++)for(int j=0;j<4;j++)m[i][j]=(i==j);int tr=0;for(int i=0;i<4;i++)tr+=m[i][i];printf("%d\n",tr);return 0;}
