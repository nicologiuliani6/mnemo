#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

struct Op{int(*f)(int,int);};
int add(int a,int b){return a+b;}int mul(int a,int b){return a*b;}
int main(void){struct Op o;o.f=add;int x=o.f(3,4);o.f=mul;int y=o.f(3,4);printf("%d %d\n",x,y);return 0;}
