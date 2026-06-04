#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int main(void){char*s="hello world";int v=0;for(int i=0;s[i];i++)if(s[i]=='o')v++;printf("%d\n",v);return 0;}
