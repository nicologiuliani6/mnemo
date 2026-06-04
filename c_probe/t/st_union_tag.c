#include <stdio.h>
#include <stdlib.h>
#include <string.h>

struct Var{int tag;union{int i;int b;}u;};
int main(void){struct Var v;v.tag=1;v.u.i=42;printf("%d %d\n",v.tag,v.u.i);return 0;}
