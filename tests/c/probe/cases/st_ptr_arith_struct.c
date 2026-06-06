#include <stdio.h>
#include <stdlib.h>
#include <string.h>

struct P{int x;int y;};
int main(void){struct P a[4]={{1,1},{2,2},{3,3},{4,4}};struct P*p=a;int s=0;for(int i=0;i<4;i++){s+=(p+i)->x;}printf("%d\n",s);return 0;}
