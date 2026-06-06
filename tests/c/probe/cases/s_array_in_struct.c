#include <stdio.h>
#include <stdlib.h>
#include <string.h>

struct V{int data[4];int len;};
int main(void){struct V v;v.len=4;for(int i=0;i<4;i++)v.data[i]=i*10;int s=0;for(int i=0;i<v.len;i++)s+=v.data[i];printf("%d\n",s);return 0;}
