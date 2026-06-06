#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int main(void){int s=0;for(int i=0;i<8;i++)s+=(1<<i);unsigned x=0xFF00;for(int i=0;i<4;i++)s+=(x>>(i*4))&0xF;printf("%d\n",s);return 0;}
