#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int ack(int m,int nn){if(m==0)return nn+1;if(nn==0)return ack(m-1,1);return ack(m-1,ack(m,nn-1));}
int main(void){printf("%d %d %d\n",ack(2,3),ack(3,3),ack(1,5));return 0;}
