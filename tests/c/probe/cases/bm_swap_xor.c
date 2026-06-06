#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int main(void){int a=5,b=9;a^=b;b^=a;a^=b;printf("%d %d\n",a,b);return 0;}
