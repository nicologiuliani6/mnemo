#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int main(void){int x=5;int*p=&x;int*q=p;*p=10;*q+=5;printf("%d\n",x);return 0;}
