#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int sum2d(int*p,int n){int s=0;for(int i=0;i<n;i++)s+=p[i];return s;}
int main(void){int m[2][3]={{1,2,3},{4,5,6}};printf("%d\n",sum2d(&m[0][0],6));return 0;}
