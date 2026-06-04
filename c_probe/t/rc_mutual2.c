#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int f(int);int g(int n){return n==0?1:n-f(g(n-1));}
int f(int n){return n==0?0:n-g(f(n-1));}
int main(void){printf("%d %d\n",f(10),g(10));return 0;}
