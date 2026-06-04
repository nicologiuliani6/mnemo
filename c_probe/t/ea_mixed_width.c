#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int main(void){uint8_t a=200;uint16_t b=60000;uint32_t c=4000000000u;printf("%u %u %u\n",(unsigned)(a+100),(unsigned)(b+10000),c+1000000000u);return 0;}
