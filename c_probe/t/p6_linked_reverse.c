#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

struct N{int v;int nx;};
int main(void){struct N p[5];for(int i=0;i<5;i++){p[i].v=i+1;p[i].nx=i+1;}p[4].nx=-1;
int head=0,prev=-1;while(head!=-1){int nx=p[head].nx;p[head].nx=prev;prev=head;head=nx;}
int s=0,c=prev;while(c!=-1){s=s*10+p[c].v;c=p[c].nx;}printf("%d\n",s);return 0;}
