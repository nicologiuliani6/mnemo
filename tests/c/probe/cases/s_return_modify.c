#include <stdio.h>
#include <stdlib.h>
#include <string.h>

struct P{int x;int y;};
struct P scale(struct P p,int f){p.x*=f;p.y*=f;return p;}
int main(void){struct P p={2,3};struct P q=scale(p,4);printf("%d %d %d %d\n",p.x,p.y,q.x,q.y);return 0;}
