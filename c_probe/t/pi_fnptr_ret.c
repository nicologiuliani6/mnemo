// SKIP fn che ritorna fn-ptr a valore runtime (pick(1)) — limite noto, scalar fn-ptr runtime non supportato
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int add(int a,int b){return a+b;}int mul(int a,int b){return a*b;}
int(*pick(int op))(int,int){return op?mul:add;}
int main(void){int(*f)(int,int)=pick(1);int(*g)(int,int)=pick(0);printf("%d %d\n",f(3,4),g(3,4));return 0;}
