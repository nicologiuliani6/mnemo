#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

struct A{int v;};struct B{struct A a;int w;};struct C{struct B b;int z;};
int main(void){struct C c={{{5},6},7};c.b.a.v=50;printf("%d %d %d\n",c.b.a.v,c.b.w,c.z);return 0;}
