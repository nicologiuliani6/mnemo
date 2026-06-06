#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

uint32_t rotl(uint32_t x,int n){return (x<<n)|(x>>(32-n));}
int main(void){printf("%08X %08X\n",rotl(0x12345678u,8),rotl(0xABCDEF01u,16));return 0;}
