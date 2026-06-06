#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int main(void){int r=3,c=4;int*m=malloc(sizeof(int)*r*c);for(int i=0;i<r;i++)for(int j=0;j<c;j++)m[i*c+j]=i*c+j;int s=0;for(int i=0;i<r*c;i++)s+=m[i];printf("%d\n",s);free(m);return 0;}
