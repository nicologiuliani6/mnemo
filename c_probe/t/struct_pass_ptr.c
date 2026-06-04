#include <stdio.h>

struct P{int x;int y;};
void inc(struct P*p){p->x++;p->y++;}
int main(void){struct P p={5,6};inc(&p);printf("%d %d\n",p.x,p.y);return 0;}
