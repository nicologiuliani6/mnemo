#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int main(void){unsigned x=0;x|=(1u<<3);x|=(1u<<7);x&=~(1u<<3);x^=(1u<<5);
printf("%u %d %d\n",x,(x>>7)&1,(x>>3)&1);return 0;}
