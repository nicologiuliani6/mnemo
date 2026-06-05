#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

struct S{int a,b,c;};
int main(void){struct S s={1,2,3};int*p=&s.b;*p=20;int*q=&s.a;printf("%d %d %d %d\n",s.a,s.b,s.c,*q);return 0;}
