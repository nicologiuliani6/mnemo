#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int main(void){int a=17,b=42;a^=b;b^=a;a^=b;printf("%d %d\n",a,b);return 0;}
