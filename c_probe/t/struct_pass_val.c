#include <stdio.h>

struct P{int x;int y;};
int sum(struct P p){return p.x+p.y;}
int main(void){struct P p={5,6};printf("%d\n",sum(p));return 0;}
