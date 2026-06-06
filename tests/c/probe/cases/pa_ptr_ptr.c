#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

void set(int**pp,int*target){*pp=target;}
int main(void){int a=1,b=2;int*p=&a;set(&p,&b);*p=99;printf("%d %d\n",a,b);return 0;}
