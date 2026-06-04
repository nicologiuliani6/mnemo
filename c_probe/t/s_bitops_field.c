#include <stdio.h>
#include <stdlib.h>
#include <string.h>

struct Flags{int a;int b;};
int main(void){struct Flags f={0xF0,0x0F};printf("%d %d\n",f.a|f.b,f.a&f.b);return 0;}
