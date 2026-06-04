#include <stdio.h>
#include <stdlib.h>
#include <string.h>

union U{int i;char c;};
struct S{union U u;int tag;};
int main(void){struct S s;s.u.i=300;s.tag=1;printf("%d %d\n",s.u.i,s.tag);return 0;}
