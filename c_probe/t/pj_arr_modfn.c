#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

void dbl(int*a,int n){for(int i=0;i<n;i++)a[i]*=2;}
int main(void){int x[5]={1,2,3,4,5};dbl(x,5);int s=0;for(int i=0;i<5;i++)s+=x[i];printf("%d\n",s);return 0;}
