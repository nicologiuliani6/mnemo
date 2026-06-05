#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

struct Vec{int d[4];};
struct Vec scale(struct Vec v,int k){for(int i=0;i<4;i++)v.d[i]*=k;return v;}
int main(void){struct Vec a={{1,2,3,4}};struct Vec b=scale(a,3);
printf("%d %d %d %d | %d %d %d %d\n",a.d[0],a.d[1],a.d[2],a.d[3],b.d[0],b.d[1],b.d[2],b.d[3]);return 0;}
