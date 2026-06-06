#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

struct Node{int val;int next;};
int main(void){struct Node pool[10];int free=0;int head=-1;for(int i=0;i<5;i++){int n=free++;pool[n].val=(i+1)*7;pool[n].next=head;head=n;}int s=0,c=head;while(c!=-1){s+=pool[c].val;c=pool[c].next;}printf("%d\n",s);return 0;}
