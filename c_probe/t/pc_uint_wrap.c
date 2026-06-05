// SKIP uint8_t/uint16_t = unsigned int (32-bit) in mnemo: 250+10=260 non 4 (no wrap a 8/16 bit) — limite type-width (char 8-bit ok, ma typedef→unsigned int)
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int main(void){uint8_t a=250;a+=10;uint16_t b=65530;b+=10;printf("%u %u\n",a,b);return 0;}
