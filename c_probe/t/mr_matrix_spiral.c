#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int main(void){int m[3][3]={{1,2,3},{4,5,6},{7,8,9}};int sum=0;for(int i=0;i<3;i++)sum+=m[0][i]+m[2][i]+m[i][0]+m[i][2];sum-=m[0][0]+m[0][2]+m[2][0]+m[2][2];printf("%d\n",sum);return 0;}
