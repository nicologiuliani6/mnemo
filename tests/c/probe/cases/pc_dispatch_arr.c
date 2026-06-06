#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int sq(int x){return x*x;}int cube(int x){return x*x*x;}int neg(int x){return -x;}
int main(void){int(*ops[3])(int)={sq,cube,neg};int s=0;for(int i=0;i<3;i++)s+=ops[i](3);printf("%d\n",s);return 0;}
