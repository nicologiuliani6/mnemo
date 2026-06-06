#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

struct Node{int val,next;};
int main(void){struct Node pool[5]={{10,1},{20,2},{30,3},{40,4},{50,-1}};
int cur=0,s=0;while(cur!=-1){s+=pool[cur].val;cur=pool[cur].next;}printf("%d\n",s);return 0;}
