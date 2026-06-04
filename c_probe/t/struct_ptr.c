#include <stdio.h>

struct P{int x;int y;};
int main(void){struct P p={3,4};struct P*q=&p;q->x=10;printf("%d %d\n",p.x,q->y);return 0;}
