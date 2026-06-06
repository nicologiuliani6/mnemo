#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

typedef struct{int x,y;}Point;
int main(void){Point p={3,4};Point q=p;q.x=10;printf("%d %d %d %d\n",p.x,p.y,q.x,q.y);return 0;}
