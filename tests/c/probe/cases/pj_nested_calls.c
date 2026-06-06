#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int f(int x){return x+1;}int g(int x){return x*2;}int h(int x){return x-3;}
int main(void){printf("%d\n",f(g(h(10))));return 0;}
