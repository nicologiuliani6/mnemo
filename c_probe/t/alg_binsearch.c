#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int bs(int*a,int n,int x){int lo=0,hi=n-1;while(lo<=hi){int m=(lo+hi)/2;if(a[m]==x)return m;if(a[m]<x)lo=m+1;else hi=m-1;}return -1;}
int main(void){int a[7]={1,3,5,7,9,11,13};printf("%d %d %d\n",bs(a,7,7),bs(a,7,1),bs(a,7,8));return 0;}
