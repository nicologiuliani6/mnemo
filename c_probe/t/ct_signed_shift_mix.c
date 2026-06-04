#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int main(void){int a=-256;printf("%d %d %d\n",a>>1,a>>4,a>>8);unsigned u=0xFF00;printf("%u\n",u>>4);return 0;}
