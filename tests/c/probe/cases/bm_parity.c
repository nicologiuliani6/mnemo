#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int par(unsigned x){x^=x>>16;x^=x>>8;x^=x>>4;x^=x>>2;x^=x>>1;return x&1;}
int main(void){printf("%d %d %d\n",par(0x7),par(0xF),par(0x1234));return 0;}
