#include <stdio.h>

struct P{int x;};
int main(void){struct P p={0};for(int i=0;i<5;i++)p.x+=i;printf("%d\n",p.x);return 0;}
