#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int main(void){unsigned int x=0xFFFFFFFFu;x+=2;unsigned int y=0;y-=1;
printf("%u %u\n",x,y);return 0;}
