#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

struct Node{int val,next;};
int main(void){struct Node g[5]={{10,1},{20,2},{30,3},{40,4},{50,-1}};
int s=0,cur=0;while(cur!=-1){s+=g[cur].val;cur=g[cur].next;}printf("%d\n",s);return 0;}
