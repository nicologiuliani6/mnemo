#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int classify(int x){return x<0?-1:x==0?0:x<10?1:x<100?2:3;}
int main(void){int s=0;int v[6]={-5,0,5,50,500,9};for(int i=0;i<6;i++)s=s*10+(classify(v[i])+1);printf("%d\n",s);return 0;}
