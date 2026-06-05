#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

struct Cell{int v,m;};
int main(void){struct Cell grid[3][3];for(int i=0;i<3;i++)for(int j=0;j<3;j++){grid[i][j].v=i*3+j;grid[i][j].m=(i==j);}
int s=0;for(int i=0;i<3;i++)for(int j=0;j<3;j++)if(grid[i][j].m)s+=grid[i][j].v;printf("%d\n",s);return 0;}
