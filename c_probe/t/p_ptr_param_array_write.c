#include <stdio.h>
#include <stdlib.h>
#include <string.h>

void fill(int*a,int n,int v){for(int i=0;i<n;i++)a[i]=v+i;}
int main(void){int a[5];fill(a,5,100);int s=0;for(int i=0;i<5;i++)s+=a[i];printf("%d\n",s);return 0;}
