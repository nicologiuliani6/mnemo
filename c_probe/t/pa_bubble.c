#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int main(void){int a[8]={5,2,8,1,9,3,7,4};
for(int i=0;i<8;i++)for(int j=0;j<7-i;j++)if(a[j]>a[j+1]){int t=a[j];a[j]=a[j+1];a[j+1]=t;}
for(int i=0;i<8;i++)printf("%d",a[i]);printf("\n");return 0;}
