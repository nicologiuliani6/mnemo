#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int main(void){uint32_t x=0x1234ABCD;int counts[16]={0};for(int i=0;i<8;i++){counts[(x>>(i*4))&0xF]++;}int nz=0;for(int i=0;i<16;i++)if(counts[i])nz++;printf("%d\n",nz);return 0;}
