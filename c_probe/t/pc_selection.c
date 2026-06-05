#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int main(void){int a[7]={64,25,12,22,11,90,1};
for(int i=0;i<6;i++){int mi=i;for(int j=i+1;j<7;j++)if(a[j]<a[mi])mi=j;int t=a[i];a[i]=a[mi];a[mi]=t;}
for(int i=0;i<7;i++)printf("%d ",a[i]);printf("\n");return 0;}
