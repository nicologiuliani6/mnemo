#include <stdio.h>
#include <stdlib.h>
#include <string.h>

void setp(int**pp,int*target){*pp=target;}
int main(void){int x=0;int*p;setp(&p,&x);*p=77;printf("%d\n",x);return 0;}
