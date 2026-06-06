#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int main(void){int a=-1;unsigned b=1;int r1=(a<(int)b);unsigned c=10,d=20;int r2=(c-d>5);
printf("%d %d %u\n",r1,r2,c-d);return 0;}
