#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

struct Color{unsigned r:8,g:8,b:8;};
int main(void){struct Color c={255,128,64};int lum=(c.r*30+c.g*59+c.b*11)/100;printf("%u %u %u %d\n",c.r,c.g,c.b,lum);return 0;}
