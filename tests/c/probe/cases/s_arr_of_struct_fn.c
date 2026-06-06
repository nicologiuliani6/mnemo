#include <stdio.h>
#include <stdlib.h>
#include <string.h>

struct P{int x;int y;};
int sumall(struct P*a,int n){int s=0;for(int i=0;i<n;i++)s+=a[i].x+a[i].y;return s;}
int main(void){struct P a[3]={{1,2},{3,4},{5,6}};printf("%d\n",sumall(a,3));return 0;}
