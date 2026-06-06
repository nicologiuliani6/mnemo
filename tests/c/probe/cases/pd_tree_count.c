#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

struct N{int l,r;};struct N t[7]={{1,2},{3,4},{5,6},{-1,-1},{-1,-1},{-1,-1},{-1,-1}};
int cnt(int i){if(i<0)return 0;return 1+cnt(t[i].l)+cnt(t[i].r);}
int main(void){printf("%d\n",cnt(0));return 0;}
