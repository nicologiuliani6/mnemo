#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

struct C{int v;};struct B{struct C*c;};struct A{struct B*b;};
int main(void){struct C c={7};struct B b;b.c=&c;struct A a;a.b=&b;
a.b->c->v*=6;printf("%d\n",a.b->c->v);return 0;}
