#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

typedef int* intptr;
int main(void){int x=42;intptr p=&x;*p+=8;printf("%d\n",x);return 0;}
