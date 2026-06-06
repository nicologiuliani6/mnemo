// SKIP fn-ptr come campo struct (ops[i].f()): dispatch su campo non implementato
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int add(int a,int b){return a+b;}int mul(int a,int b){return a*b;}
struct Op{int(*f)(int,int);int tag;};
int main(void){struct Op ops[2]={{add,1},{mul,2}};int r=0;
for(int i=0;i<2;i++)r+=ops[i].f(3,4);printf("%d\n",r);return 0;}
