#include <stdio.h>
#include <stdlib.h>
#include <string.h>

unsigned f(unsigned a,unsigned b){return a*b;}
int main(void){printf("%u\n",f(100000u,100000u));return 0;}
