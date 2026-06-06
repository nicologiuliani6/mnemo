#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int main(void){int n=10;int*a=malloc(sizeof(int)*n);for(int i=0;i<n;i++)a[i]=i*i;int s=0;for(int i=0;i<n;i++)s+=a[i];printf("%d\n",s);free(a);return 0;}
