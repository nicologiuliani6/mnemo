#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int add(int a,int b){return a+b;}int mul(int a,int b){return a*b;}int mx(int a,int b){return a>b?a:b;}
int main(void){int(*ops[3])(int,int)={add,mul,mx};int acc=2;for(int i=0;i<9;i++)acc=ops[i%3](acc,i);printf("%d\n",acc);return 0;}
