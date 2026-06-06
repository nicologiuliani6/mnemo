#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int sq(int x){return x*x;}int cube(int x){return x*x*x;}
int main(void){int s=0;for(int i=1;i<=4;i++)s+=(i%2)?sq(i):cube(i);printf("%d\n",s);return 0;}
