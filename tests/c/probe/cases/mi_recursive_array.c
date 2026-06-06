#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int sumarr(int*a,int n){if(n==0)return 0;return a[0]+sumarr(a+1,n-1);}
int main(void){int a[5]={1,2,3,4,5};printf("%d\n",sumarr(a,5));return 0;}
