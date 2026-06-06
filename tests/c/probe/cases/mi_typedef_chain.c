#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef int myint;typedef myint*intptr;
int main(void){myint x=5;intptr p=&x;*p=99;printf("%d\n",x);return 0;}
