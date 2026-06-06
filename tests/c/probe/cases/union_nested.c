#include <stdio.h>

struct In{int a;int b;};
union U{struct In s;int raw;};
int main(void){union U u;u.s.a=100;u.s.b=200;printf("%d %d %d\n",u.s.a,u.s.b,u.raw);return 0;}
