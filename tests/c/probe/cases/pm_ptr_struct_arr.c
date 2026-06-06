#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

struct R{int v;};
int main(void){struct R arr[5]={{1},{2},{3},{4},{5}};struct R*p=arr;int s=0;
for(int i=0;i<5;i++)s+=(p+i)->v;printf("%d\n",s);return 0;}
