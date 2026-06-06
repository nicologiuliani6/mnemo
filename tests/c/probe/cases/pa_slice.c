#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

static int sum(const int*p,int n){int s=0;while(n--)s+=*p++;return s;}
int main(void){int a[10]={1,2,3,4,5,6,7,8,9,10};printf("%d %d %d\n",sum(a,10),sum(a+3,4),sum(a,0));return 0;}
