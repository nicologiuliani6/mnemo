#include <stdio.h>
#include <stdlib.h>
#include <string.h>

struct N{int val;int next;};
int main(void){struct N pool[5];for(int i=0;i<5;i++){pool[i].val=(i+1)*10;pool[i].next=i+1;}pool[4].next=-1;int cur=0,sum=0;while(cur!=-1){sum+=pool[cur].val;cur=pool[cur].next;}printf("%d\n",sum);return 0;}
