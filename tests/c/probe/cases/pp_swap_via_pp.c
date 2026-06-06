#include <stdio.h>
#include <stdlib.h>
#include <string.h>

void sw(int**a,int**b){int*t=*a;*a=*b;*b=t;}
int main(void){int x=1,y=2;int*p=&x,*q=&y;sw(&p,&q);printf("%d %d\n",*p,*q);return 0;}
