#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int sz(void){return 7;}
int main(void){int n=sz();int*a=malloc(sizeof(int)*n);for(int i=0;i<n;i++)a[i]=i;
int s=0;for(int i=0;i<n;i++)s+=a[i];printf("%d\n",s);free(a);return 0;}
