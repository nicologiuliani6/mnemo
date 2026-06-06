#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

static int* maxptr(int*a,int n){int*m=a;for(int i=1;i<n;i++)if(a[i]>*m)m=a+i;return m;}
int main(void){int a[7]={3,1,4,1,5,9,2};int*p=maxptr(a,7);printf("%d %ld\n",*p,(long)(p-a));return 0;}
