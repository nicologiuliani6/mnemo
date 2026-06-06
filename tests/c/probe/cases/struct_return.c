#include <stdio.h>

struct P{int x;int y;};
struct P mk(int a,int b){struct P p={a,b};return p;}
int main(void){struct P p=mk(7,8);printf("%d %d\n",p.x,p.y);return 0;}
