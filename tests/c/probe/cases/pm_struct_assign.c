#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

struct P{int x,y,z;};
int main(void){struct P a={1,2,3};struct P b;b=a;b.x=10;printf("%d %d %d %d\n",a.x,b.x,b.y,b.z);return 0;}
