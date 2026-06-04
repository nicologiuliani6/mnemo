#include <stdio.h>
#include <stdlib.h>
#include <string.h>

struct N{int v;};
int main(void){struct N*a=malloc(sizeof(struct N)*3);for(int i=0;i<3;i++)a[i].v=(i+1)*100;printf("%d\n",a[0].v+a[1].v+a[2].v);free(a);return 0;}
