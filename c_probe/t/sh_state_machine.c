#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

struct SM{int state;int count;};
void step(struct SM*m,int in){if(m->state==0&&in)m->state=1;else if(m->state==1&&!in){m->state=0;m->count++;}}
int main(void){struct SM m={0,0};int seq[8]={1,0,1,1,0,1,0,0};for(int i=0;i<8;i++)step(&m,seq[i]);printf("%d\n",m.count);return 0;}
