#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int main(void){unsigned char b[4]={0xDE,0xAD,0xBE,0xEF};uint32_t v=0;for(int i=0;i<4;i++)v=(v<<8)|b[i];printf("%08X\n",v);return 0;}
