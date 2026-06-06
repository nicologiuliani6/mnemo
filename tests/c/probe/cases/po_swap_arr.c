#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

void swap(int*a,int*b){int t=*a;*a=*b;*b=t;}
int main(void){int a[6]={6,5,4,3,2,1};for(int i=0;i<3;i++)swap(&a[i],&a[5-i]);
int s=0;for(int i=0;i<6;i++)s+=a[i]*(i+1);printf("%d\n",s);return 0;}
