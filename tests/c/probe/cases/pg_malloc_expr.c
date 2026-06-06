#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int main(void){int n=5;int*a=malloc(sizeof(int)*(n+1));for(int i=0;i<=n;i++)a[i]=i*2;
int s=0;for(int i=0;i<=n;i++)s+=a[i];printf("%d\n",s);free(a);return 0;}
