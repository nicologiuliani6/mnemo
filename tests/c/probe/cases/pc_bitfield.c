#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

struct Flags{unsigned a:3;unsigned b:5;unsigned c:8;};
int main(void){struct Flags f;f.a=5;f.b=20;f.c=200;printf("%u %u %u\n",f.a,f.b,f.c);return 0;}
