// SKIP (unsigned char)i a 8 bit: cast scalare = passthrough (Mnemo word-VM 64-bit, no trunc del target) — divergenza type-width
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int main(void){int i=300;char c=(char)i;unsigned u=(unsigned)c;int back=(int)(unsigned char)i;
printf("%d %d %d\n",(int)c,u,back);return 0;}
