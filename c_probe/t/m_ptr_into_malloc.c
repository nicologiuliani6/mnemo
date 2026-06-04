#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int main(void){int*a=malloc(sizeof(int)*4);int*p=a+2;*p=99;printf("%d\n",a[2]);free(a);return 0;}
