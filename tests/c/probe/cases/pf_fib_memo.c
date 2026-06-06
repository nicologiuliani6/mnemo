#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int memo[40];
int fib(int n){if(n<2)return n;if(memo[n])return memo[n];return memo[n]=fib(n-1)+fib(n-2);}
int main(void){printf("%d %d %d\n",fib(10),fib(20),fib(30));return 0;}
