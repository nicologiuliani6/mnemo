#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int add(int a,int b){return a+b;}int mul(int a,int b){return a*b;}
int main(void){printf("%d\n",add(mul(2,3),mul(add(1,2),4)));return 0;}
