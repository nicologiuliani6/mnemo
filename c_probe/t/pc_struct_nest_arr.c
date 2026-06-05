#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

struct Row{int cells[4];};struct Grid{struct Row rows[3];};
int main(void){struct Grid g;for(int i=0;i<3;i++)for(int j=0;j<4;j++)g.rows[i].cells[j]=i*4+j;
int s=0;for(int i=0;i<3;i++)for(int j=0;j<4;j++)s+=g.rows[i].cells[j];printf("%d\n",s);return 0;}
