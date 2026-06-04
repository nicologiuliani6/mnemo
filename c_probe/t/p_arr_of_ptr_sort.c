#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int main(void){int a=3,b=1,c=2;int*p[3]={&a,&b,&c};for(int i=0;i<3;i++)for(int j=i+1;j<3;j++)if(*p[i]>*p[j]){int*t=p[i];p[i]=p[j];p[j]=t;}printf("%d %d %d\n",*p[0],*p[1],*p[2]);return 0;}
