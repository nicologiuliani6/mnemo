#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int add(int a,int b){return a+b;}int sub(int a,int b){return a-b;}int mul(int a,int b){return a*b;}int dv(int a,int b){return a/b;}
int main(void){int(*ops[4])(int,int)={add,sub,mul,dv};int r=100;for(int i=0;i<4;i++)r=ops[i](r,2);printf("%d\n",r);return 0;}
