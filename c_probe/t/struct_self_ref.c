#include <stdio.h>

struct N{int v;int next;};
int main(void){struct N a[3];a[0].v=10;a[0].next=1;a[1].v=20;a[1].next=2;a[2].v=30;a[2].next=-1;int i=0,s=0;while(i>=0){s+=a[i].v;i=a[i].next;}printf("%d\n",s);return 0;}
