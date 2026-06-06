#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

struct P{int x,y;};
int main(void){struct P a[10];struct P*p=&a[2];struct P*q=&a[7];printf("%d\n",(int)(q-p));return 0;}
