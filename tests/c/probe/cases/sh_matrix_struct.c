#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

struct M{int d[2][2];};
struct M mul(struct M a,struct M b){struct M r;for(int i=0;i<2;i++)for(int j=0;j<2;j++){r.d[i][j]=0;for(int k=0;k<2;k++)r.d[i][j]+=a.d[i][k]*b.d[k][j];}return r;}
int main(void){struct M a={{{1,2},{3,4}}},b={{{5,6},{7,8}}};struct M c=mul(a,b);printf("%d %d %d %d\n",c.d[0][0],c.d[0][1],c.d[1][0],c.d[1][1]);return 0;}
