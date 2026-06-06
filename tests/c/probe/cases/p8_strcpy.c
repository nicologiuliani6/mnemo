#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int main(void){char dst[16];const char*src="hello";int i=0;while((dst[i]=src[i]))i++;
printf("%s %d\n",dst,i);return 0;}
