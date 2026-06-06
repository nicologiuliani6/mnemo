#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

struct P{int x,y;};
struct P mk(int a,int b){struct P p;p.x=a;p.y=b;return p;}
int main(void){struct P q=mk(3,7);printf("%d %d %d\n",q.x,q.y,q.x+q.y);return 0;}
