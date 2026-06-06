#include <stdio.h>

struct Inner{int a;int b;};
struct Outer{struct Inner in;int c;};
int main(void){struct Outer o={{1,2},3};printf("%d %d %d\n",o.in.a,o.in.b,o.c);return 0;}
