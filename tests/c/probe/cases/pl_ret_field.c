#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

struct P{int x,y;};
struct P mk(int a){struct P p;p.x=a;p.y=a*a;return p;}
int main(void){struct P q=mk(5);printf("%d %d\n",q.x,q.y);return 0;}
