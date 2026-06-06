#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int main(void){int a[10];for(int i=0;i<10;i++)a[i]=i+1;
for(int i=0,j=9;i<j;i++,j--){int t=a[i];a[i]=a[j];a[j]=t;}
int s=0;for(int i=0;i<10;i++)s+=a[i]*(i+1);printf("%d\n",s);return 0;}
