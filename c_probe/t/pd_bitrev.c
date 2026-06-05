#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

unsigned rev8(unsigned x){unsigned r=0;for(int i=0;i<8;i++){r=(r<<1)|(x&1);x>>=1;}return r;}
int main(void){printf("%u %u %u\n",rev8(1),rev8(0x80),rev8(0xAB));return 0;}
