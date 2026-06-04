#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int main(void){int s=0;for(int k=0;k<3;k++){int*a=malloc(sizeof(int)*4);for(int i=0;i<4;i++)a[i]=k*10+i;for(int i=0;i<4;i++)s+=a[i];free(a);}printf("%d\n",s);return 0;}
