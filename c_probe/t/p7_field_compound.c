#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

struct C{int n;};
int main(void){struct C c={10};struct C*p=&c;p->n+=5;p->n*=2;p->n-=3;printf("%d\n",c.n);return 0;}
