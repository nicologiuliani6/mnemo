#include <stdio.h>
#include <stdlib.h>
#include <string.h>

struct P{int x;int y;};
int main(void){struct P a={1,2};struct P b=a;b.x=99;printf("%d %d %d %d\n",a.x,a.y,b.x,b.y);return 0;}
