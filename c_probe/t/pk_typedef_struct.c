#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

typedef struct{int a,b;}Pair;
int main(void){Pair p={3,4};Pair*q=&p;q->a+=10;printf("%d %d\n",p.a,q->b);return 0;}
