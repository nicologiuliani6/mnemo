#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int main(void){int a=-16;unsigned b=0xFFFFFFF0u;printf("%d %u %d\n",a>>2,b>>2,(-100)>>3);return 0;}
