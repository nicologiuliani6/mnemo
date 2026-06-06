// SKIP (int)0xFFFFFFFFu = -1 in gcc (int 32-bit) vs 4294967295 in mnemo (int 64-bit) — divergenza int-width documentata
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int main(void){unsigned char b=200;b+=100;int i=b;unsigned u=0xFFFFFFFFu;int si=(int)u;
printf("%d %u %d\n",i,u,si);return 0;}
