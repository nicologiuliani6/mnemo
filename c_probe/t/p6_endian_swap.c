#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

uint32_t bswap(uint32_t x){return ((x&0xFF)<<24)|((x&0xFF00)<<8)|((x>>8)&0xFF00)|((x>>24)&0xFF);}
int main(void){printf("%08X\n",bswap(0x12345678u));return 0;}
