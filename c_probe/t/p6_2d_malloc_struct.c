#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

struct Cell{int v;};
int main(void){int R=3,C=3;struct Cell*g=malloc(sizeof(struct Cell)*R*C);for(int i=0;i<R*C;i++)g[i].v=i;int tr=0;for(int i=0;i<R;i++)tr+=g[i*C+i].v;printf("%d\n",tr);free(g);return 0;}
