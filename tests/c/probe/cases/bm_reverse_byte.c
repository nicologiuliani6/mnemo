#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

unsigned char rb(unsigned char b){b=(b&0xF0)>>4|(b&0x0F)<<4;b=(b&0xCC)>>2|(b&0x33)<<2;b=(b&0xAA)>>1|(b&0x55)<<1;return b;}
int main(void){printf("%d %d\n",rb(1),rb(0x80));return 0;}
