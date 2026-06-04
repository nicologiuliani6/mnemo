#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int collatz(int n){int s=0;while(n!=1){if(n%2==0)n/=2;else n=3*n+1;s++;}return s;}
int main(void){printf("%d %d\n",collatz(27),collatz(6));return 0;}
