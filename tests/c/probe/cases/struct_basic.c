#include <stdio.h>

struct P{int x;int y;};
int main(void){struct P p={3,4};printf("%d %d\n",p.x,p.y);return 0;}
