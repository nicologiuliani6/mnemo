#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int main(void){int n=4;int*a=malloc(sizeof(int)*n);int*b=malloc(sizeof(int)*n);
for(int i=0;i<n;i++){a[i]=i;b[i]=i*i;}int s=0;for(int i=0;i<n;i++)s+=a[i]+b[i];printf("%d\n",s);
free(a);free(b);return 0;}
