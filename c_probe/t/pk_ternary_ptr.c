#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int main(void){int a=1,b=2;int*p=(a<b)?&a:&b;*p=99;printf("%d %d\n",a,b);return 0;}
