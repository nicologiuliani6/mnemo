#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int f0(int x){return x;}int f1(int x){return x+1;}int f2(int x){return x*2;}
int main(void){int(*fns[3])(int)={f0,f1,f2};int v=5;for(int i=0;i<6;i++)v=fns[i%3](v);printf("%d\n",v);return 0;}
