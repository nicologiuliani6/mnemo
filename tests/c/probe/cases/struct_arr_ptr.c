#include <stdio.h>

struct P{int x;int y;};
int main(void){struct P a[3]={{1,2},{3,4},{5,6}};struct P*p=a;p++;printf("%d %d\n",p->x,p->y);return 0;}
