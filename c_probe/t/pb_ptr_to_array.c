#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int sumrow(int(*row)[4],int i){int s=0;for(int j=0;j<4;j++)s+=row[i][j];return s;}
int main(void){int m[3][4]={{1,2,3,4},{5,6,7,8},{9,10,11,12}};
printf("%d %d %d\n",sumrow(m,0),sumrow(m,1),sumrow(m,2));return 0;}
