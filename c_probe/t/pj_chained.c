#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int main(void){int a,b,c;a=b=c=5;a+=b+=c;printf("%d %d %d\n",a,b,c);return 0;}
