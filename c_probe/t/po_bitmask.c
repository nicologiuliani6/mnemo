#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int main(void){unsigned packed=0;packed|=(5<<0);packed|=(3<<4);packed|=(7<<8);
int a=packed&0xF,b=(packed>>4)&0xF,c=(packed>>8)&0xF;printf("%d %d %d\n",a,b,c);return 0;}
