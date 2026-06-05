#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int g=100;
void inc(int d){g+=d;}
int get(void){return g;}
int main(void){for(int i=1;i<=5;i++)inc(i);printf("%d %d\n",get(),g);return 0;}
