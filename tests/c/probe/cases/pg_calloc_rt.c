#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int main(void){int n=5;int*a=calloc(n,sizeof(int));int s=0;for(int i=0;i<n;i++)s+=a[i];
for(int i=0;i<n;i++)a[i]=i*3;for(int i=0;i<n;i++)s+=a[i];printf("%d\n",s);free(a);return 0;}
