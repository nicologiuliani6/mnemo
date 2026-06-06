#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int f(int x){return x*x;}int g(int x){return x+1;}
int main(void){int s=0;for(int i=-2;i<=2;i++)s+=(i<0?f(i):i==0?100:g(i));printf("%d\n",s);return 0;}
