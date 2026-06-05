#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int main(void){int m[3][3]={{1,2},{4},{7,8,9}};int s=0;for(int i=0;i<3;i++)for(int j=0;j<3;j++)s+=m[i][j];printf("%d\n",s);return 0;}
