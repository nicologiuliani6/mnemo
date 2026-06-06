#include <stdio.h>
#include <stdlib.h>
#include <string.h>

struct P{int x;int y;};
int main(void){struct P a[3]={{1,2}};printf("%d %d %d %d\n",a[0].x,a[0].y,a[1].x,a[2].y);return 0;}
