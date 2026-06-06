#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int main(void){unsigned int packed=0;int r=5,g=10,b=15;
packed=(r<<8)|(g<<4)|b;int xr=(packed>>8)&0xF,xg=(packed>>4)&0xF,xb=packed&0xF;
printf("%d %d %d %u\n",xr,xg,xb,packed);return 0;}
