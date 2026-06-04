#include <stdio.h>

void dbl(int*a,int n){for(int i=0;i<n;i++)a[i]*=2;}
int main(void){int a[4]={1,2,3,4};dbl(a,4);printf("%d %d %d %d\n",a[0],a[1],a[2],a[3]);return 0;}
