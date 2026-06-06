#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

struct B{int v;};struct A{struct B*b;};
int main(void){struct B b={42};struct A a;a.b=&b;a.b->v+=8;printf("%d\n",a.b->v);return 0;}
