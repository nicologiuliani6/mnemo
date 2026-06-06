#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int sum(int m[][3],int rows){int s=0;for(int i=0;i<rows;i++)for(int j=0;j<3;j++)s+=m[i][j];return s;}
int main(void){int a[2][3]={{1,2,3},{4,5,6}};printf("%d\n",sum(a,2));return 0;}
