#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int main(void){int cap=2,len=0;int*a=malloc(sizeof(int)*cap);for(int i=0;i<10;i++){if(len==cap){cap*=2;int*na=malloc(sizeof(int)*cap);for(int k=0;k<len;k++)na[k]=a[k];free(a);a=na;}a[len++]=i*i;}int s=0;for(int i=0;i<len;i++)s+=a[i];printf("%d\n",s);free(a);return 0;}
