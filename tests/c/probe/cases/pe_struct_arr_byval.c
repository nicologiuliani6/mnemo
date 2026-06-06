#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

struct Vec{int d[4];};
int dot(struct Vec a,struct Vec b){int s=0;for(int i=0;i<4;i++)s+=a.d[i]*b.d[i];return s;}
int main(void){struct Vec u={{1,2,3,4}},v={{5,6,7,8}};printf("%d\n",dot(u,v));return 0;}
