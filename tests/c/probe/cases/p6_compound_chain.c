#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int main(void){int x=64;x>>=2;x|=3;x^=0xF;x&=0x3F;x+=10;x*=2;printf("%d\n",x);return 0;}
