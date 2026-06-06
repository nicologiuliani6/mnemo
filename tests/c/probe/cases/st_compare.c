#include <stdio.h>
#include <stdlib.h>
#include <string.h>

struct P{int x;int y;};
int eq(struct P a,struct P b){return a.x==b.x&&a.y==b.y;}
int main(void){struct P a={1,2},b={1,2},c={3,4};printf("%d %d\n",eq(a,b),eq(a,c));return 0;}
