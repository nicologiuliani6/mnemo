#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

struct P{int x,y;};
int total(struct P*a,int n){int s=0;for(int i=0;i<n;i++)s+=a[i].x+a[i].y;return s;}
int main(void){struct P arr[3]={{1,2},{3,4},{5,6}};printf("%d\n",total(arr,3));return 0;}
