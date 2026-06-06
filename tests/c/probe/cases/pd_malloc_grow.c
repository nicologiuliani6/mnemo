#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

int main(void){int*a=malloc(sizeof(int)*4);for(int i=0;i<4;i++)a[i]=i*i;
int*b=malloc(sizeof(int)*8);for(int i=0;i<4;i++)b[i]=a[i];for(int i=4;i<8;i++)b[i]=i*i;free(a);
int s=0;for(int i=0;i<8;i++)s+=b[i];printf("%d\n",s);free(b);return 0;}
