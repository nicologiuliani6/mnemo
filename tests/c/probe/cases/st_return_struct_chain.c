#include <stdio.h>
#include <stdlib.h>
#include <string.h>

struct P{int x;int y;};
struct P add(struct P a,struct P b){struct P r={a.x+b.x,a.y+b.y};return r;}
int main(void){struct P a={1,2},b={3,4},c={5,6};struct P r=add(add(a,b),c);printf("%d %d\n",r.x,r.y);return 0;}
