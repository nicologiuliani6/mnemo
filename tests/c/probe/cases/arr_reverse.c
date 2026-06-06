#include <stdio.h>

int main(void){int a[5]={1,2,3,4,5};for(int i=0,j=4;i<j;i++,j--){int t=a[i];a[i]=a[j];a[j]=t;}for(int i=0;i<5;i++)printf("%d",a[i]);printf("\n");return 0;}
