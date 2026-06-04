#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int main(void){int a[4]={1,2,3,4};int*p=a;int*q=a+3;int s=0;while(p<=q){s+=*p;p++;}printf("%d\n",s);return 0;}
