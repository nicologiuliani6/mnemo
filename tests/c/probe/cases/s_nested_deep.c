#include <stdio.h>
#include <stdlib.h>
#include <string.h>

struct A{int v;};struct B{struct A a;};struct C{struct B b;};
int main(void){struct C c;c.b.a.v=7;printf("%d\n",c.b.a.v);return 0;}
