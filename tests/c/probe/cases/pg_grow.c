#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int main(void){int n=4;int*a=malloc(sizeof(int)*n);for(int i=0;i<n;i++)a[i]=i+1;
int m=8;int*b=malloc(sizeof(int)*m);for(int i=0;i<n;i++)b[i]=a[i];for(int i=n;i<m;i++)b[i]=i+1;
free(a);int s=0;for(int i=0;i<m;i++)s+=b[i];free(b);printf("%d\n",s);return 0;}
