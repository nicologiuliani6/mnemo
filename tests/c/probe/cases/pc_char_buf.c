#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int main(void){char buf[20];int i=0;for(int v=12345;v>0;v/=10)buf[i++]=v%10+'0';buf[i]=0;
for(int a=0,b=i-1;a<b;a++,b--){char t=buf[a];buf[a]=buf[b];buf[b]=t;}printf("%s\n",buf);return 0;}
