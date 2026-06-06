#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int main(void){int n=6;int*p=malloc(sizeof(int)*n);for(int i=0;i<n;i++)*(p+i)=i*i;
int s=0;for(int i=0;i<n;i++)s+=*(p+i);printf("%d\n",s);free(p);return 0;}
