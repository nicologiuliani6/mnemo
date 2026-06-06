#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int main(void){int R=3,C=4;int*m=malloc(sizeof(int)*R*C);for(int i=0;i<R;i++)for(int j=0;j<C;j++)m[i*C+j]=i*10+j;int mx=0;for(int i=0;i<R*C;i++)if(m[i]>mx)mx=m[i];printf("%d\n",mx);free(m);return 0;}
