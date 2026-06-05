#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

struct P{int x,y,z;};
int main(void){struct P p={.z=9,.x=1};printf("%d %d %d\n",p.x,p.y,p.z);return 0;}
