#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int f0(int x){return x;}int f1(int x){return x*2;}int f2(int x){return x+10;}
struct T{int(*ops[3])(int);};
int main(void){struct T t;t.ops[0]=f0;t.ops[1]=f1;t.ops[2]=f2;int v=5;
for(int i=0;i<3;i++)v=t.ops[i](v);printf("%d\n",v);return 0;}
