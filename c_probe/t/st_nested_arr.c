// SKIP: struct-array annidato con campo-array (g.rows[i].cells[j]) niche
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

struct Row{int cells[3];};
struct Grid{struct Row rows[2];};
int main(void){struct Grid g;for(int i=0;i<2;i++)for(int j=0;j<3;j++)g.rows[i].cells[j]=i*3+j;int s=0;for(int i=0;i<2;i++)for(int j=0;j<3;j++)s+=g.rows[i].cells[j];printf("%d\n",s);return 0;}
