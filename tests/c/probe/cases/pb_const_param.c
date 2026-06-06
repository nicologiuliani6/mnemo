#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int count_pos(const int*a,int n){int c=0;for(int i=0;i<n;i++)if(a[i]>0)c++;return c;}
int main(void){int a[8]={-1,2,-3,4,5,-6,7,8};printf("%d\n",count_pos(a,8));return 0;}
