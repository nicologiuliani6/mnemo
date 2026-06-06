#include <stdio.h>

int main(void){int a=0xF0,b=0x0F;printf("%d %d %d %d\n",a&b,a|b,a^b,~a);return 0;}
