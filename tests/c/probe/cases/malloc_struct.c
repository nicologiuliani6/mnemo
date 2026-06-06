#include <stdio.h>
#include <stdlib.h>
#include <string.h>

struct P{int x;int y;};
int main(void){struct P*p=malloc(sizeof(struct P));p->x=3;p->y=4;printf("%d\n",p->x*p->y);free(p);return 0;}
