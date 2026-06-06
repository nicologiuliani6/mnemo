#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

unsigned np2(unsigned x){x--;x|=x>>1;x|=x>>2;x|=x>>4;x|=x>>8;x|=x>>16;return x+1;}
int main(void){printf("%u %u %u\n",np2(5),np2(17),np2(1000));return 0;}
