// SKIP union int<->byte type-punning: word-model 1 cella=1 word, non aliasa sub-word
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

union U{int i;unsigned char b[4];};
int main(void){union U u;u.i=0x12345678;int s=0;for(int k=0;k<4;k++)s+=u.b[k];
printf("%d %02X\n",s,u.b[0]);return 0;}
