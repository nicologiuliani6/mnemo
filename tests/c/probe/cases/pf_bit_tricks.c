#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int popcount(unsigned x){int c=0;while(x){x&=x-1;c++;}return c;}
int main(void){printf("%d %d %d\n",popcount(0xFF),popcount(0x1234),popcount(0));return 0;}
