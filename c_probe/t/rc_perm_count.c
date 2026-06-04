#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int fact(int n){return n<=1?1:n*fact(n-1);}
int main(void){printf("%d %d\n",fact(6),fact(0));return 0;}
