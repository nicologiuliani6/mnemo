#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

uint32_t crc(const char*s){uint32_t c=0xFFFFFFFFu;while(*s){c^=(unsigned char)*s++;for(int i=0;i<8;i++)c=(c>>1)^(0xEDB88320u&(-(c&1)));}return ~c;}
int main(void){printf("%08X\n",crc("123456789"));return 0;}
