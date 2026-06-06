#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

struct KV{int k;int v;};
int lookup(int key){static const struct KV tab[4]={{1,100},{2,200},{3,300},{4,400}};
for(int i=0;i<4;i++)if(tab[i].k==key)return tab[i].v;return -1;}
int main(void){printf("%d %d %d\n",lookup(2),lookup(4),lookup(9));return 0;}
