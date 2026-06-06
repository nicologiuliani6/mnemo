#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

struct N{int v;};
int main(void){struct N a={1},b={2},c={3};struct N*arr[3]={&a,&b,&c};
int s=0;for(int i=0;i<3;i++)s+=arr[i]->v;arr[1]->v=20;s+=arr[1]->v;printf("%d\n",s);return 0;}
