#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int main(void){int x=42;int*p=&x;int**pp=&p;**pp=100;(**pp)+=5;printf("%d\n",x);return 0;}
