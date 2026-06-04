#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

unsigned br(unsigned x){unsigned r=0;for(int i=0;i<32;i++){r=(r<<1)|(x&1);x>>=1;}return r;}
int main(void){printf("%08X\n",br(0x00000001u));return 0;}
