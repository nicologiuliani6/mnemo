#include <stdio.h>
#include <stdlib.h>
#include <string.h>

struct{int x;int y;}p={5,6};
int main(void){printf("%d\n",p.x+p.y);return 0;}
