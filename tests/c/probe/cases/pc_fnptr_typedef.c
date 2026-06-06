#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

typedef int(*BinOp)(int,int);
int add(int a,int b){return a+b;}int sub(int a,int b){return a-b;}
int apply(BinOp f,int a,int b){return f(a,b);}
int main(void){printf("%d %d\n",apply(add,7,3),apply(sub,7,3));return 0;}
