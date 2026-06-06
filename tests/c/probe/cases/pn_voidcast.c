#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int main(void){int x=42;void*v=&x;int*p=(int*)v;*p+=8;printf("%d\n",x);return 0;}
