#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

void qs(int*a,int lo,int hi){if(lo>=hi)return;int p=a[hi],i=lo;for(int j=lo;j<hi;j++)if(a[j]<p){int t=a[i];a[i]=a[j];a[j]=t;i++;}int t=a[i];a[i]=a[hi];a[hi]=t;qs(a,lo,i-1);qs(a,i+1,hi);}
int main(void){int a[8]={5,2,8,1,9,3,7,4};qs(a,0,7);for(int i=0;i<8;i++)printf("%d",a[i]);printf("\n");return 0;}
