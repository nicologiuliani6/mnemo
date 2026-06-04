#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int main(void){uint64_t v=0x0123456789ABCDEFull;for(int i=15;i>=0;i--)printf("%X",(unsigned)((v>>(i*4))&0xF));printf("\n");return 0;}
